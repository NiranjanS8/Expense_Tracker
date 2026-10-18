# Phase 6 scoping — which write operations the assistant may ever propose

Status: Tier A shipped (read-only drafts). Tiers B–D are **not** implemented; Phase 6
remains gated on explicit owner approval after a reviewed read-only launch
(`plan.md` §6, §7).

This note records *which* operations could be handed to the assistant and why most
of the API surface is deliberately excluded.

## Current state

The assistant cannot write. This service exposes no write endpoint, holds no write
credential, and its financial client only issues `GET`. Tier A goes one step
closer without crossing that line.

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

## Tier B — the first real writes, if Tier A is reviewed and accepted

| Operation | Endpoint | Why it is a candidate | Care needed |
| --- | --- | --- | --- |
| Create expense | `POST /expenses` | Reversible via delete; highest demand | Idempotency key (double-submit creates two rows) |
| Set monthly budget | `PUT /budgets/{month}` | Month-keyed upsert, idempotent by construction | Show old vs. new; `POST /budgets` also exists for a first insert |

These two cover most "log this for me" demand at the lowest risk.

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

- **The model never performs the write.** It emits a *proposal*; execution runs on a
  separate path with no model in the loop.
- **Proposed values are auditable back to the user's message**, and the confirmation
  UI shows the literal values so a misparse is caught by a human.
- **Approval is bound to a canonical hash of the arguments plus the user and the
  resource id**, so nothing can be swapped between proposal and execution.
- **Idempotency key per proposal**, so a double-submit cannot double-create.
- **Re-read before applying**; on a timeout report "unknown — check your records"
  rather than retrying blindly.
- **Every execution emits an audit event.**
- **Write tools stay behind a disabled-by-default flag** until each one is reviewed.

## Recommended sequencing

1. Review Tier A running against real data (read-only launch).
2. Enable Tier B behind a flag, starting with create-expense and set-budget.
3. Hold Tier C until the approval machinery has a track record.
4. Treat Tier D as permanently excluded.
