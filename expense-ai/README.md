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

Not implemented yet: the LangGraph workflow, read-only financial tools,
conversation persistence, and streaming. `/api/v1/chat` and the conversation
routes require authentication and then return `501`, deliberately, rather than
fabricating a response.

## Requirements

- Python 3.12
- [uv](https://docs.astral.sh/uv/)
- The Spring Boot backend reachable (default `http://localhost:9090`)

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
uv run ruff check .
```

Tests never touch the network: the Spring Boot API is stubbed with an explicit
`httpx.MockTransport`.

## Configuration

All settings are read from the environment or `.env`. See `.env.example`.

| Variable | Purpose |
| --- | --- |
| `EXPENSE_TRACKER_BASE_URL` | Spring Boot base URL (scheme + host + port) |
| `EXPENSE_TRACKER_CONTEXT_PATH` | Servlet context path (default `/api`) |
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
