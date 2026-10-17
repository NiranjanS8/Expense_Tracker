# expense-ai

Read-only AI assistant for the existing Expense Tracker Spring Boot backend.
FastAPI handles HTTP; a bounded LangGraph workflow controls model execution. This
service never connects to the financial database — Spring Boot remains the only
route to financial data and the only authority for tokens. Conversation state is
stored in the service's own PostgreSQL database, separate from the financial
schema.

## Status

Phase 1 — service foundation. Implemented:

- FastAPI app with a versioned `/api/v1` surface and root `/health/live` + `/health/ready`.
- Typed errors with a stable, secret-free JSON envelope.
- Bearer authentication via Spring Boot introspection (`GET /users/me`), with a
  short-lived token cache. **The JWT signing secret is never held by this service.**
- Structured JSON logging, correlation IDs (`X-Correlation-Id`) propagated inbound
  and upstream, and token redaction.
- Request-size limits, per-user chat rate limiting, and CORS configuration.
- An abstract model-provider layer supporting **OpenAI, Claude (Anthropic),
  Mistral, DeepSeek and Gemini**, plus a deterministic `fake` provider.
- A multi-stage container image and a compose file for local development, plus CI
  that lints, type-checks and tests both services.

Phase 2 — read-only tools. Implemented:

- A typed, allowlisted tool layer over the verified Spring Boot endpoints, with no
  database driver in the service at all.
- Strict argument schemas that reject unknown fields, so an identity can never
  arrive from model output.
- Bounded inputs (date ranges, amounts, pagination, free text, list sizes) and
  bounded, read-only retries on the upstream client.

Phase 3 — the bounded assistant. Implemented:

- A single LangGraph workflow (`app/agent/`) with explicit nodes: load context,
  classify intent, plan, validate arguments, authorize, execute one tool, verify,
  compose, persist. No autonomous loop; tool calls and graph steps are bounded.
- Owner-scoped conversation persistence in PostgreSQL via SQLAlchemy, with Alembic
  migrations and a `/api/v1/conversations` read/delete API.
- Streaming chat at `POST /api/v1/chat` using typed server-sent events.
- Grounding guarantees: financial figures come only from tool results, and a data
  question that retrieved nothing is refused rather than answered from the model's
  memory.

Phase 4 — evaluation and hardening. Implemented:

- A versioned evaluation dataset (`evals/datasets/`) replayed deterministically in
  CI, covering tool selection, grounding, empty results, backend failures,
  unsupported requests and prompt injection.
- Adversarial and resilience suites: unregistered tools, identity/URL arguments,
  oversized input, upstream and provider failures, and client disconnect.
- In-process metrics exposed in Prometheus text format at `GET /metrics` (closed
  unless `METRICS_ENABLED=true`), with token and estimated-cost counters.
- Optional trace export (off by default); see [`docs/observability.md`](docs/observability.md)
  and [`docs/operations.md`](docs/operations.md).

Every answer is a read-only answer. Nothing in this service mutates financial data.

## Tools

`app/tools/` exposes eight read-only tools. Each one validates its arguments,
forwards the caller's token to Spring Boot, and returns a typed result or a typed,
client-safe error.

| Tool | Verified endpoint |
| --- | --- |
| `get_spending_summary` | `GET /expenses/summary` |
| `search_expenses` | `GET /expenses` |
| `get_category_breakdown` | `GET /dashboard/categories` |
| `get_dashboard_summary` | `GET /dashboard/summary` |
| `get_budget_status` | `GET /budgets/current`, `GET /budgets/{month}`, `GET /budgets?year=` |
| `get_goal_progress` | `GET /goals`, `GET /goals/{id}` |
| `get_recurring_expenses` | `GET /recurring-expenses` |
| `get_existing_insights` | `GET /insights/summary` |

`app/tools/registry.py` is the allowlist: a tool that is not registered cannot be
invoked, and no tool accepts a user identifier. A month with no budget, and a
resource that belongs to another user, are both normal answers rather than
failures.

## Chat API

| Method | Path | Purpose |
| --- | --- | --- |
| `POST` | `/api/v1/chat` | Submit a message; streams the answer as server-sent events |
| `GET` | `/api/v1/conversations` | List the caller's conversations |
| `GET` | `/api/v1/conversations/{id}` | Read one conversation and its messages |
| `DELETE` | `/api/v1/conversations/{id}` | Delete one conversation |

All four require `Authorization: Bearer <token>`. A conversation id owned by
another user is reported as `404`, never `403`, so ids cannot be probed.

`POST /api/v1/chat` body: `{ "message": "...", "conversation_id": "optional" }`.
Omit `conversation_id` to start a new conversation (its title is taken from the
first message); supply it to continue one.

### Streaming events

The response is `text/event-stream` with typed events:

| Event | Payload |
| --- | --- |
| `message_start` | `{ conversationId }` |
| `status` | `{ stage, tool? }` — e.g. `planning`, `retrieving` |
| `token` | `{ text }` — a fragment of the answer as the model produces it |
| `message_complete` | `{ conversationId, messageId, content, termination, toolCalls }` |
| `error` | `{ code, message, correlationId }` |

Authentication and conversation ownership are resolved *before* the stream opens,
so `401`/`404` arrive as normal JSON responses. Events never contain prompts,
tokens, stack traces, or internal tool arguments.

Every adapter decodes its provider's own stream format, reassembling tool-call
arguments that arrive in fragments, so answers arrive as they are written.

> Deltas are provisional: `message_complete.content` is the authoritative answer
> and must replace whatever was streamed, because a turn the policy replaces is
> retracted there. A turn that produces no deltas sends its whole answer as a
> single `token` instead. Prose from an ungrounded planning call is never
> published at all, so invented figures cannot appear even transiently.

## The workflow

`app/agent/graph.py` wires one bounded `StateGraph`:

```
load_context -> classify_intent -> plan -> validate_arguments -> authorize_tool
                                        -> execute_tool -> verify_result
                                        -> (loop, bounded) -> plan
              -> compose_answer -> persist_and_trace
```

- `classify_intent` is a deterministic keyword gate: only finance questions may
  spend a tool call.
- The model is given the allowlisted tool schemas and may request a tool; the
  registry validates its arguments and the graph enforces the per-turn tool
  budget (`AGENT_MAX_TOOL_CALLS`) and a recursion limit (`AGENT_RECURSION_LIMIT`).
- A data question that produced no tool result is answered with a deterministic
  refusal, so the model can never present invented figures. Tool and provider
  failures become safe, typed messages instead of fabricated totals.
- `persist_and_trace` runs only on success, so a failed turn stores nothing.

## Conversation persistence and migrations

Conversation state lives in the AI service's own PostgreSQL database
(`DATABASE_URL`); Spring Boot's financial tables are never touched. Two tables
are managed by Alembic:

- `conversations` — id, owner id, title, status, timestamps.
- `messages` — id, conversation id, role (`user`/`assistant`), content, timestamp.

Every query is owner-scoped at the repository boundary. Only user-visible messages
are stored: no chain-of-thought, no tool payloads, no tokens.

```bash
uv run alembic upgrade head          # apply migrations
uv run alembic revision --autogenerate -m "describe the change"
```

## Observability

Metrics are recorded in-process and rendered in the Prometheus text format at
`GET /metrics`, which is closed unless `METRICS_ENABLED=true`. Labels are drawn
from a closed set (endpoint names, tool names, outcomes, providers), never from
user identifiers or amounts. Optional tracing is off by default because it exports
prompts and retrieved financial figures to a third party. See
[`docs/observability.md`](docs/observability.md) for the metric catalog, tracing
setup and redaction, and [`docs/operations.md`](docs/operations.md) for retention,
deployment and the failure runbook.

## Requirements

- Python 3.12
- [uv](https://docs.astral.sh/uv/)
- The Spring Boot backend reachable (default `http://localhost:9090`)
- PostgreSQL for conversation state (the bundled compose file provides one)
- Docker, only if you want the container image

## Setup

```bash
cd expense-ai
uv sync
cp .env.example .env   # then fill in values; never commit .env
uv run alembic upgrade head   # create the AI-owned schema
```

## Run

```bash
uv run alembic upgrade head
uv run uvicorn app.main:app --reload --port 8080
```

Health checks:

```bash
curl http://localhost:8080/health/live
curl http://localhost:8080/health/ready
```

## Test

```bash
uv run pytest
uv run ruff format --check .
uv run ruff check .
uv run mypy
```

Tests never touch the network: the Spring Boot API is stubbed with an explicit
`httpx.MockTransport`.

The evaluation dataset in `evals/datasets/read_only_assistant.json` is replayed by
`tests/agent_eval/`; add a case there to record the expected behaviour of a new
prompt.

## Docker

The image is built from the pinned `uv.lock`, runs as a non-root user, and needs
no credentials to start (the default provider is `fake`). Alembic migrations and
the application ship in the image.

```bash
docker build -t expense-ai:local .

# or, using the bundled compose file (starts PostgreSQL and applies migrations)
docker compose up -d
curl http://localhost:8080/health/live
docker compose down
```

The Spring Boot application is deliberately **not** containerized and keeps
running on the host. From inside the container it is reached at
`host.docker.internal:9090`, which compose configures automatically.

If host port `8080` is already in use, override it:

```bash
EXPENSE_AI_PORT=8081 docker compose up -d
```

The container health check probes only `/health/live`. `/health/ready` also
requires a usable model provider, so a missing credential surfaces as
*not ready* rather than as a restarting container.

## Continuous integration

`.github/workflows/ci.yml` runs two jobs on pushes to `main` and on pull requests:

- `expense-ai` — `uv sync --frozen`, format check, lint, `mypy`, `pytest`.
- `backend` — `mvn test` for the existing Spring Boot application, which uses the
  `test` profile on H2 and needs no external database.

## Configuration

All settings are read from the environment or `.env`. See `.env.example`.

| Variable | Purpose |
| --- | --- |
| `EXPENSE_TRACKER_BASE_URL` | Spring Boot base URL (scheme + host + port) |
| `EXPENSE_TRACKER_CONTEXT_PATH` | Servlet context path (default `/api`) |
| `EXPENSE_TRACKER_TIMEOUT_SECONDS` | Total read timeout for an upstream call |
| `EXPENSE_TRACKER_MAX_RETRIES` | Retries for transport failures and `502`/`503`/`504` (never for `4xx`) |
| `EXPENSE_TRACKER_RETRY_BACKOFF_SECONDS` | Base delay between retries |
| `IDENTITY_CACHE_TTL_SECONDS` | TTL for the token→identity cache (`0` disables it) |
| `DATABASE_URL` | AI-owned PostgreSQL URL (SQLAlchemy async URL) |
| `DATABASE_ECHO` | Log SQL statements (default `false`) |
| `AUTO_CREATE_SCHEMA` | Build the schema inline; `false` in deployment (Alembic owns it), `true` in tests |
| `AGENT_MAX_TOOL_CALLS` | Tool calls allowed per turn |
| `AGENT_RECURSION_LIMIT` | Upper bound on graph steps per turn |
| `AGENT_HISTORY_MESSAGES` | Prior messages of context sent to the model |
| `CONVERSATION_LIST_LIMIT` | Maximum conversations returned by the list endpoint |
| `CONVERSATION_MESSAGE_LIMIT` | Maximum messages returned by the detail endpoint |
| `CONVERSATION_TITLE_MAX_LENGTH` | Truncation length for derived conversation titles |
| `LLM_PROVIDER` | `openai` \| `anthropic` \| `mistral` \| `deepseek` \| `gemini` \| `fake` |
| `<PROVIDER>_API_KEY` | Credential for the selected provider only |
| `MAX_REQUEST_BYTES` | Rejects larger request bodies with `413` |
| `CHAT_RATE_LIMIT_PER_MINUTE` | Per-user chat limit |
| `METRICS_ENABLED` | Expose `GET /metrics` (Prometheus text); `false` by default |
| `LANGSMITH_TRACING` | Enable optional trace export; off by default |
| `LANGSMITH_API_KEY` | Credential for the tracing backend |
| `LANGSMITH_PROJECT` | Tracing project name |
| `LANGSMITH_ENDPOINT` | Tracing backend URL; set it for a self-hosted instance |

## Model providers

`app/integrations/model_provider/` defines one `ModelProvider` interface and
provider-agnostic types (`ChatRequest`, `ChatResponse`, `ToolCall`, `ToolSpec`).
Provider wire formats are confined to their adapters:

- `openai_compatible.py` — OpenAI, Mistral and DeepSeek (shared `/chat/completions` shape)
- `anthropic_provider.py` — Claude Messages API
- `gemini.py` — Google Generative Language API
- `fake.py` — deterministic, credential-free

Adding a provider means adding one settings block, one adapter, and one registry
entry. Nothing else changes.

## Authentication model

The frontend sends its existing Spring Boot access token to this service. This
service does not verify signatures; it asks the authority:

1. `Authorization: Bearer <token>` is extracted (and wrapped so it cannot be logged).
2. `GET /api/users/me` is called with the same token; success yields the trusted
   user ID and email.
3. The identity is cached briefly, keyed by a SHA-256 fingerprint of the token.
4. Downstream Spring Boot calls forward the original token, so Spring Boot
   re-validates and enforces ownership on every request.

User identity is never taken from chat text, request bodies, or tool arguments.

## Known limitations

- The chat rate limiter is in-process; replace it with a shared store before
  horizontal scaling.
- `/health/ready` validates configuration and pings the AI database; it does not
  probe Spring Boot, so a Java restart cannot flap this service's readiness.
- Readiness requires the selected provider's credential to be present.
- `token` deltas are provisional (see *Streaming events*): a client must
  reconcile to `message_complete.content` rather than assume the deltas always
  concatenate to it.
- Token and cost metrics for a streamed call come from the provider's own usage
  reporting. OpenAI and DeepSeek are asked for it explicitly; Mistral's endpoint
  is not sent that option, because an unsupported field would fail the request,
  so its streamed usage is recorded only if the provider sends it anyway.
- For a data question the model may only answer from tool results, so an
  ambiguous data question is met with a deterministic "rephrase with a period"
  refusal rather than a model-written clarifying question.
- Conversation history is bounded when sent to the model
  (`AGENT_HISTORY_MESSAGES`) and when returned by the API
  (`CONVERSATION_MESSAGE_LIMIT`); a retention/cleanup policy for stored
  conversations is not yet automated.
- `GET /metrics` has no built-in access control; when enabled it must be reached
  only from a trusted network.
- The evaluation suite is deterministic and scripted; a model-backed evaluation of
  answer quality, latency and cost is not part of CI.
- Optional tracing exports prompts and the financial figures tools returned to a
  third party; leave it off, or point it at a self-hosted instance, in production.
