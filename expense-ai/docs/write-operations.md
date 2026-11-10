# Confirmed write operations

Status: **implemented, disabled by default.** The assistant can propose four
changes — create an expense, set a monthly budget, pause or resume a recurring
expense, and add a category — and execute one only after the owner approves that
exact proposal. `plan.md` §6 defines the gate; this note records the design that
satisfies it.

Related: [`phase-6-scoping.md`](phase-6-scoping.md) (why these actions),
`docs/deployment.md` (operational runbook).

## What the assistant may write

| Action | Effect | Spring Boot endpoint |
| --- | --- | --- |
| `create_expense` | Adds one expense | `POST /expenses` |
| `set_budget` | Sets one month's budget, creating it if absent | `GET /budgets/{month}` then `POST /budgets` or `PUT /budgets/{month}` |
| `set_recurring_status` | Pauses or resumes one recurring rule | `GET /recurring-expenses` then `PATCH /recurring-expenses/{id}/status` |
| `create_category` | Adds one custom category | `POST /categories` |

Nothing else is enabled: no deletes, no edits to existing expenses, no goals, no
recurring-rule creation or amount changes, no smart rules, no account changes.
Deletes have no undo path in the product, and `PUT /expenses/{id}` is a full
replace with no `updatedAt` or ETag, so a concurrent edit would be silently
overwritten.

## The model is not in the write path

There is no write tool in the model's allowlist. The proposal is parsed from the
caller's message by the same deterministic code the draft path uses
(`app/agent/writes.py`), so:

- every value in a proposal is traceable to text the user typed;
- the model cannot invent an amount, date, description or category that then
  persists;
- the path works with the model provider unavailable or unconfigured.

When the parser cannot produce a complete change, the turn asks for the missing
piece or falls back to the existing form draft. A miss is therefore a question or
a draft, never a write.

Two of the actions change an existing record rather than add one, so they need a
specific target. `set_recurring_status` matches the rule the caller named against
the owner's own `GET /recurring-expenses` list; if the name matches nothing and
they have more than one rule, the assistant lists them and asks which one. It
never guesses between several records.

## Lifecycle

```
chat turn ──► parse ──► approval_requests row (pending) ──► proposal event
                                                              │
                              approve ──► conditional claim ──┤
                              cancel  ──► conditional cancel ─┤
                              (TTL)   ──► expired             │
                                                              ▼
                                          execute (one attempt, no retry)
                                                              │
                          ┌───────────────┬───────────────────┼────────────────┐
                          ▼               ▼                   ▼                ▼
                      executed         failed             unknown          cancelled
```

Every transition is persisted with a timestamp and logged as an audit event.

## Binding and single use

A proposal stores its canonical arguments and a SHA-256 hash over:

```
owner_id + action + resource_id + canonical(arguments)
```

- The approve endpoint takes **only** the approval id. There are no client-supplied
  arguments to replay, so an approval cannot be reused with changed values.
- The hash is recomputed immediately before execution; a row altered in storage is
  rejected as a conflict.
- The owner is part of the hash *and* every SQL statement. Another user's id is a
  `404`, never a `403`.
- The claim is a conditional update:
  `… SET status='executing' WHERE id=? AND owner_id=? AND status='pending' AND expires_at > now`.
  Exactly one concurrent approval can win; the others receive `409`.

An approval expires after `APPROVAL_TTL_SECONDS` (default 600 s) and can be
cancelled while pending. Cancelled and expired approvals can never execute.

## Execution semantics

**Revalidation.** A budget approval re-reads the month before writing and chooses
`PUT` (exists) or `POST` (missing). If another writer creates the month between
that read and the create, the one safe retry is a `PUT` to the same amount. An
expense approval re-reads the category list when it named a category; if that
category has since disappeared, nothing is written. A recurring-status request is
answered with "already paused/resumed" instead of a card when the rule is already
in that state; the check runs again at execution time in case it changed meanwhile,
and makes no request at all.

**Reconciliation for declarative changes.** Pausing, resuming and adding a
category all describe an end state rather than an increment, so after a lost
response the assistant can settle the outcome itself instead of leaving it
unknown. It re-reads the rule's `active` flag, or the category list by name, and
reports `executed` when the change is present and `failed` when it is absent. The
write is still never retried in that second attempt; only a read is repeated.

**Ambiguous outcomes.** Writes are never retried. A timeout or a 5xx on
`create_expense` or `set_budget` is recorded as `unknown`, with a message telling
the owner to check their records. This is the only honest report there: the
request reached the point where it may have committed.

**Definite failures.** A 4xx, an invalid session, or a rate limit means nothing was
saved. The backend's own validation message (truncated) is shown to its owner.

**No duplicate on resubmission.** A second approval of a resolved request returns
`409` with its current state and performs no write.

## API

All routes require `Authorization: Bearer <token>` and are `404` unless
`WRITE_OPERATIONS_ENABLED=true`.

| Method | Path | Purpose |
| --- | --- | --- |
| `GET` | `/api/v1/approvals?conversationId=` | Still-pending approvals for one conversation |
| `GET` | `/api/v1/approvals/{id}` | One approval (owner-scoped) |
| `POST` | `/api/v1/approvals/{id}/approve` | Execute once, if pending and unexpired |
| `POST` | `/api/v1/approvals/{id}/cancel` | Cancel while pending |

The chat stream also emits:

| Event | Payload |
| --- | --- |
| `proposal` | `{ id, action, summary, details, consequences, expiresAt }` |

`details` is the list of `{ label, value }` pairs the UI renders verbatim; the
approval, not the client, is the source of truth at execution time.

## Data model

`approval_requests` lives in the AI service's own database (Alembic revision
`0002_create_approval_requests`). It carries the owner, conversation, action,
resource, canonical arguments, hash, display summary, details, consequences,
status, idempotency key, and timestamps.

Statuses: `pending`, `executing`, `executed`, `failed`, `unknown`, `cancelled`,
`expired`.

## Enabling

```dotenv
WRITE_OPERATIONS_ENABLED=false          # default
APPROVAL_TTL_SECONDS=600
APPROVAL_RATE_LIMIT_PER_MINUTE=10
```

Set the flag to `true` only after the read-only launch has been reviewed. Then run
`alembic upgrade head` before rolling the service, and confirm:

1. a record request returns a `proposal` event and **no** upstream write;
2. approving once writes once; approving again returns `409`;
3. cancelling prevents execution;
4. an unrelated user's approval id returns `404`.

## Observability

Structured audit lines (never amounts or descriptions):

```
event=write_proposal_created approval_id=… user_id=… action=… binding=<hash prefix>
event=write_approved         approval_id=… user_id=… action=… binding=…
event=write_executed         approval_id=… user_id=… action=… resource_id=…
event=write_failed           approval_id=… user_id=… action=…
event=write_outcome_unknown  approval_id=… user_id=… action=…
event=write_cancelled        approval_id=… user_id=…
```

Metrics: `expense_ai_write_proposals_total{action}` and
`expense_ai_write_executions_total{action,outcome}`.

## Known limitations

- **No undo in the assistant.** A created expense can only be removed through the
  Expenses screen, which is a hard delete. A budget can only be changed again.
- **`set_budget` sets, it does not add.** "Add 500 to my budget" is parsed as
  setting the month to 500. The confirmation card shows the literal value.
- **Category matching is literal.** A category is used only if its name appears in
  the message; otherwise the backend's smart-category rules decide, and a write
  with no matching rule fails safely with the backend's message.
- **Recurring rules are matched by name, literally.** The rule's description (or
  category name) must appear in the message, or the owner must have exactly one
  rule. A renamed rule changes the match; two identical names are reported as
  ambiguous rather than picked.
- **Pausing stops future occurrences only.** Expenses a rule already generated are
  untouched, and resuming starts from the next scheduled date — there is no
  backfill. The confirmation card says so.
- **A new category is just a name.** It cannot set a smart rule, colour, or icon;
  duplicates are rejected by the backend and surface as a failed approval.
- **Payment method defaults to `OTHER` when unstated**, and the card says
  `Other (not specified)` so the owner can cancel.
- **Ten-minute window.** After expiry the user must ask again; proposals are not
  renewed automatically.
- **Reload shows pending only.** A resolved proposal is not re-rendered from the
  transcript; its outcome is visible in the response and in the data itself.
- **Single approver, single host.** There is no delegated approval, and the
  in-process rate limiter is per replica (see `docs/deployment.md` §9).
