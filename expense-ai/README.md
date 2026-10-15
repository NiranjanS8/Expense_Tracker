# expense-ai

Read-only AI assistant for the existing Expense Tracker Spring Boot backend.
FastAPI handles HTTP; a bounded LangGraph workflow (Phase 3) will control model
execution. This service never connects to the financial database — Spring Boot
remains the only route to financial data and the only authority for tokens.

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

Not implemented yet: the LangGraph workflow, conversation persistence, and
streaming. `/api/v1/chat` and the conversation routes require authentication and
then return `501`, deliberately, rather than fabricating a response.

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

## Requirements

- Python 3.12
- [uv](https://docs.astral.sh/uv/)
- The Spring Boot backend reachable (default `http://localhost:9090`)
- Docker, only if you want the container image

## Setup

```bash
cd expense-ai
uv sync
cp .env.example .env   # then fill in values; never commit .env
```

## Run

```bash
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

## Docker

The image is built from the pinned `uv.lock`, runs as a non-root user, and needs
no credentials to start (the default provider is `fake`).

```bash
docker build -t expense-ai:local .

# or, using the bundled compose file
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
| `LLM_PROVIDER` | `openai` \| `anthropic` \| `mistral` \| `deepseek` \| `gemini` \| `fake` |
| `<PROVIDER>_API_KEY` | Credential for the selected provider only |
| `MAX_REQUEST_BYTES` | Rejects larger request bodies with `413` |
| `CHAT_RATE_LIMIT_PER_MINUTE` | Per-user chat limit |

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
- `/health/ready` validates configuration only; it does not probe Spring Boot, so
  a backend restart cannot flap this service's readiness.
- Readiness requires the selected provider's credential to be present.
