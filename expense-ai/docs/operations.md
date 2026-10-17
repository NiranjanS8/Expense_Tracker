# Operations

How to run, monitor, and recover the AI service. Spring Boot and its financial
data are out of scope here: this service never owns or migrates them.

## Deploy

1. Apply the AI-owned schema (Alembic owns it; `AUTO_CREATE_SCHEMA` stays `false`):

   ```bash
   uv run alembic upgrade head
   ```

2. Provide configuration from the environment (see `.env.example`). At minimum:
   `DATABASE_URL`, `EXPENSE_TRACKER_BASE_URL`, `LLM_PROVIDER` and that provider's
   `*_API_KEY`. Never commit secrets.
3. Serve:

   ```bash
   uv run uvicorn app.main:app --host 0.0.0.0 --port 8080
   ```

Readiness and liveness are separate on purpose:

- `GET /health/live` — process liveness; trivial and unauthenticated.
- `GET /health/ready` — configuration and the AI database. It does **not** probe
  Spring Boot, so a Java restart cannot flap this service's readiness.

If a deployment adds tracing or the metrics endpoint, confirm
`docs/observability.md` first: both are opt-in.

## Backups and retention

The AI service owns exactly two tables, in its own database, and nothing else:

- `conversations` — id, owner id, title, status, timestamps.
- `messages` — conversation id, role (`user`/`assistant`), content, timestamp.

Policy:

- **Scope.** Only user-visible messages are stored. No prompts, tool payloads,
  amounts, tokens or chain-of-thought are persisted.
- **Access.** Every read and delete is owner-scoped at the repository boundary; a
  conversation id owned by another user is indistinguishable from a missing one
  (`404`).
- **Deletion.** `DELETE /api/v1/conversations/{id}` removes a conversation and its
  messages. Deletion is per conversation today; automated retention is an open
  item. Until it exists, treat retention as "until the user deletes it".
- **Backups.** Back up the AI database on the same schedule as other application
  state. Restores only ever target this database.
- **Migrations.** Forward-only in practice: `alembic upgrade head` on deploy.
  `alembic downgrade` exists for emergencies and has only been exercised against
  the initial revision.

## Monitor

Scrape `GET /metrics` (when `METRICS_ENABLED=true`) and watch, at least:

- `expense_ai_chat_turns_total{outcome=...}` — a rising `tool_error` or
  `model_error` share means a dependency or the provider is unhealthy.
- `expense_ai_http_request_duration_seconds` / `expense_ai_chat_turn_duration_seconds`
  — latency.
- `expense_ai_model_cost_usd_total` — estimated spend.
- `expense_ai_rate_limit_rejections_total`, `expense_ai_auth_denials_total` —
  abuse or misconfiguration.
- `GET /health/ready` — readiness.

Logs are structured JSON with a `correlationId` (also returned as
`X-Correlation-Id`) that ties a client request to its upstream calls.

## Runbook

| Symptom | Likely cause | Action |
| --- | --- | --- |
| `/health/ready` returns `503` with `model_provider` | Provider credential missing/invalid | Set the selected provider's `*_API_KEY`; confirm `LLM_PROVIDER` |
| `/health/ready` returns `503` with `database: down` | AI database unreachable | Check `DATABASE_URL`, network, and the Postgres service |
| Chat answers say the assistant is "temporarily unavailable" | Model provider outage, timeout or rate limit | Check `expense_ai_model_calls_total{outcome="error"}`; verify provider status/quota |
| Chat answers say it "couldn't retrieve the data" | Spring Boot error/timeout on the tool endpoint | Check `expense_ai_tool_calls_total{outcome=...}` and Spring Boot health |
| `429` responses | Per-user chat limit reached | Expected back-pressure; raise `CHAT_RATE_LIMIT_PER_MINUTE` if legitimate |
| `401` responses | Token missing, expired or rejected upstream | Re-authenticate; confirm Spring Boot accepts the token |

Behaviour on failure is deliberate: a data question that produced no tool result
is refused, never answered from memory, so a degraded dependency surfaces as a
safe message rather than an invented figure. A turn that fails before completion
persists nothing.

## Rollback

- Redeploy the previous image tag (`expense-ai:local` or your registry tag). Code
  and schema are the only moving parts; there is no queue or background worker.
- If a migration must be reverted, `uv run alembic downgrade -1` on the AI
  database only. Rehearse this against a copy first — it has only been exercised
  against the initial revision.
- Readiness reflects reality, so an old image that cannot reach its dependencies
  reports `not_ready` rather than serving broken answers.

## Open items

- An automated retention/cleanup policy for stored conversations.
- A shared rate-limit store (Redis) before horizontal scaling.
- LangGraph checkpointing, only if interrupt/resume is ever needed.
