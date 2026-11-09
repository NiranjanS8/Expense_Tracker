# Phase 6 scoping — which write operations the assistant may ever propose

Status: Tier A shipped (read-only drafts). **Tier B is implemented behind
`WRITE_OPERATIONS_ENABLED`, off by default**; its design and runbook live in
[`write-operations.md`](write-operations.md). Tiers C–D remain unimplemented. The
owner approval required by `plan.md` §6, §7 has been given for Tier B only.

This note records *which* operations could be handed to the assistant and why most
of the API surface is deliberately excluded.

## Current state

With writes disabled, the assistant cannot write: it has no write tool, the
financial client's read path only issues `GET`, and there is no approval surface.
With writes enabled, it can *propose* the two Tier B actions; a separate,
owner-scoped, single-use approval executes them. In both modes the model never
originates a value that persists.

## What makes a write safe enough to hand to an assistant

The verb is not what matters. Five properties are:

1. **Reversible or trivially correctable** — the user can undo it with one existing
   action. A create is reversible only when a delete exists.
2. **Value originates from the user** — the write-side of the grounding rule. If the
   model can *originate* a figure that gets persisted, fabrication has returned
   with side effects.
3. **Deterministic target** — one record, addressed by id, owned by the caller.
   Never "all matching".
4. **Idempotent or duplicate-proof** — a double-submit or a model loop must not
   create two rows.
5. **Bounded blast radius** — one field of one record. Nothing that emails data
   off-platform, exports it, or touches authentication.

## Tier A — draft only, no write path (shipped)

A record request ("add a 12.50 coffee expense yesterday") becomes a **draft**: the
values for one of the application's own forms. The chat offers a button that
pre-fills that form, and the user saves it through the existing screen.

Most of the UX benefit with none of the write risk: no approval store, no
idempotency problem, no new audit surface, and the "AI never mutates" guarantee
stays literally true. Extraction is deterministic (`app/agent/drafts.py`), so a
draft can only ever contain values the user typed.

## Tier B — the first real writes (implemented behind a flag)

| Operation | Endpoint | Why it is a candidate | Care needed |
| --- | --- | --- | --- |
| Create expense | `POST /expenses` | Reversible via delete; highest demand | Single-use approval; no retry on ambiguity; category revalidation |
| Set monthly budget | `GET` then `POST`/`PUT /budgets` | Month-keyed and duplicate-proof | Re-read the month and choose create vs update; show old → new |

These two cover most "log this for me" demand at the lowest risk. The implemented
version resolves the duplicate-submit concern at the approval layer (an atomic
claim), not with an upstream idempotency key, because the existing API has none.
Category matching is literal and a month that does not exist is created.

Tier B reuses the Tier A parser: the model is not asked to emit write arguments.

## Tier C — plausible later, needs the confirmation machinery proven first

- **Pause/resume a recurring expense** (`PATCH /recurring-expenses/{id}/status`) —
  touches no existing figure and is trivially reversible.
- **Update an expense** (`PUT /expenses/{id}`) — a full replace, not a patch, so
  every field must be resent; show the before → after.
- **Create a goal** (`POST /goals`) — declarative and deletable.
- **Update a recurring expense or goal** (`PUT`) — the consequence is future-facing
  and must be explained, not merely confirmed.
- **Smart category rules** (`POST`/`PUT`/`DELETE /smart-category-rules`) — mechanics,
  low blast radius.

## Tier D — excluded

- **Delete an expense or goal** (`DELETE /expenses/{id}`, `DELETE /goals/{id}`) —
  these are **hard deletes**: the schema has no soft-delete flag and no `@SQLDelete`,
  so the API offers no undo. Have the assistant navigate the user to the record
  instead.
- **Generate recurring expenses** (`POST /recurring-expenses/generate`) — creates N
  expenses in one call, with the worst partial-failure story.
- **Send an email report** (`POST /email-reports/send`) — moves financial data to an
  external destination.
- **Create an export job** (`POST /exports/jobs`) — data egress.
- **Register or log in** (`POST /auth/register`, `POST /auth/login`) — the assistant
  must never hold or enter credentials.

For completeness, `UserController` exposes only `GET /users/me`; there is no profile
write to consider.

## Cross-cutting requirements for any Tier B–C operation

These are the Phase 6 acceptance criteria in implementation terms:

- **The model never performs the write.** The deterministic parser emits the
  *proposal*; execution runs on a separate path with no model in the loop, and no
  write tool is registered with the model at all.
- **Proposed values are auditable back to the user's message**, and the confirmation
  UI shows the literal values so a misparse is caught by a human.
- **Approval is bound to a canonical hash of the arguments plus the user and the
  resource id**, so nothing can be swapped between proposal and execution.
- **Idempotency key per proposal**, so a double-submit cannot double-create.
- **Re-read before applying**; on a timeout report "unknown — check your records"
  rather than retrying blindly.
- **Every execution emits an audit event.**
- **The write surface stays behind a disabled-by-default flag** until each action is
  reviewed. (Tier B goes further: the model has no write tool, so the flag gates the
  proposal and approval endpoints themselves.)

## Recommended sequencing

1. ~~Review Tier A running against real data (read-only launch).~~ Done.
2. ~~Enable Tier B behind a flag, starting with create-expense and set-budget.~~ The
   code and the flag exist; enabling is an operator decision per environment.
3. Hold Tier C until the approval machinery has a track record.
4. Treat Tier D as permanently excluded.
