# Staging deployment runbook

This runbook deploys the whole Expense Tracker stack — the Spring Boot API, its
PostgreSQL database, the read-only assistant and the React app — with Docker
Compose. It is the repeatable path the Phase 5 acceptance criteria asks for:

- an authenticated user can chat with the assistant,
- streaming and errors render correctly,
- the existing Expense Tracker screens are untouched,
- the deployment is reproduced from these steps.

Everything below runs on one host. TLS, secret storage and monitoring exporters
are shown as configuration to apply, because those depend on where you host.

## 1. What gets deployed

| Service | Image / build | Reachable from | Purpose |
| --- | --- | --- | --- |
| `frontend` | `frontend/Dockerfile` (Vite build served by nginx) | host port `FRONTEND_PORT` (default `8081`) | Serves the SPA and reverse-proxies `/api` and `/ai` |
| `backend` | `backend.Dockerfile` (Maven build, Java 21) | the compose network only | Financial API, the only route to financial data |
| `financial-db` | `postgres:17-alpine` | the compose network only | Spring Boot's own PostgreSQL |
| `expense-ai` | `expense-ai/Dockerfile` (FastAPI) | the compose network, plus loopback `AI_PORT` for operators | Read-only assistant |
| `ai-db` | `postgres:17-alpine` | the compose network only | Assistant conversations and messages |

Two invariants shape this layout:

- The browser only ever talks to the frontend origin. nginx forwards `/api/*` to
  Spring Boot and `/ai/*` to the assistant (rewritten to `/api/v1/*`). One origin
  means no CORS exceptions and no token crossing an extra boundary.
- The assistant has no database credentials for the financial schema. It reaches
  financial data solely through Spring Boot with the caller's own token.

## 2. Prerequisites

- Docker Engine with Compose v2 (`docker compose version`).
- A PostgreSQL-free host: both databases run in containers with named volumes.
- Roughly 4 GB of free disk for images and volumes, and enough memory for the
  Maven and Node builds (the first `up --build` is the slow one).

## 3. First deployment

```bash
cp .env.staging.example .env.staging
# Edit .env.staging: every value marked REQUIRED, plus the provider settings.
docker compose -f compose.staging.yaml --env-file .env.staging up --build -d
```

Compose refuses to start if a `${VAR:?...}` value is missing, so a forgotten
secret fails fast instead of leaving a half-configured stack.

Check status and follow the assistant's startup (it runs `alembic upgrade head`
before serving):

```bash
docker compose -f compose.staging.yaml ps
docker compose -f compose.staging.yaml logs -f expense-ai
```

## 4. Verifying the deployment

```bash
# Assistant readiness: configuration plus its own database.
curl -fsS http://127.0.0.1:18080/health/ready

# In-process metrics in Prometheus text format.
curl -fsS http://127.0.0.1:18080/metrics | head

# Liveness.
curl -fsS http://127.0.0.1:18080/health/live
```

Then walk the acceptance path in a browser at `http://localhost:8081`:

1. Sign in. `APP_SEED_ENABLED=true` creates the demo user
   `demo@expensetracker.com` with password `Password@123`, plus sample expenses.
2. Open **Expenses**, **Budgets**, **Reports** and confirm the existing screens
   still load and edit as before.
3. Open **Assistant**. Ask `How much did I spend this month?`. The turn shows
   progress states, then the answer, with the tools that produced it listed under
   the message.
4. Press **Stop** mid-turn and confirm the turn cancels cleanly.
5. Ask a question the assistant cannot ground, and confirm it refuses instead of
   inventing figures.
6. Reload the page and reopen the conversation from the sidebar.

> With `LLM_PROVIDER=fake` the answers are deliberately synthetic (`[fake] …`),
> because the fake provider never invents financial data. It exists so the stack
> can be rehearsed with no credentials. Set a real provider and key in
> `.env.staging` to see grounded answers.

## 5. Configuration and secrets

| Variable | Required | Notes |
| --- | --- | --- |
| `FINANCIAL_DB_PASSWORD` | yes | Spring Boot's database |
| `AI_DB_PASSWORD` | yes | Assistant's database |
| `JWT_SECRET` | yes | Signs the access tokens the assistant introspects; set a long random value |
| `LLM_PROVIDER` | no | `fake` by default; one of `openai`, `anthropic`, `mistral`, `deepseek`, `gemini`, `fake` |
| `<PROVIDER>_API_KEY` | yes for a real provider | Only the selected provider's key is read |
| `JPA_DDL_AUTO` | no | `update` for a disposable staging database; `validate` anywhere the schema is managed outside the app |
| `APP_SEED_ENABLED` | no | `true` seeds the demo user and sample expenses |
| `METRICS_ENABLED` | no | Exposes `/metrics` on the assistant |
| `LANGSMITH_TRACING` / `LANGSMITH_API_KEY` | no | Off by default; sends prompts and retrieved figures to a third party (see `expense-ai/docs/observability.md`) |

`.env.staging` holds the only copy of these values and is git-ignored. For
anything beyond a rehearsal host, source them from your platform's secret store
(for example `docker compose … --env-file <(your-secret-cli get …)`), rotate
`JWT_SECRET` and the database passwords on the schedule your policy requires, and
never bake them into an image — neither Dockerfile copies an env file, and both
`.dockerignore` files exclude them.

## 6. TLS

Terminate TLS in front of the frontend container; the stack itself speaks plain
HTTP on the compose network. Any ingress that supports streaming works. With
nginx:

```nginx
server {
    listen 443 ssl;
    server_name staging.example.com;

    ssl_certificate     /etc/ssl/certs/staging.crt;
    ssl_certificate_key /etc/ssl/private/staging.key;

    location / {
        proxy_pass http://127.0.0.1:8081;
        proxy_http_version 1.1;
        proxy_set_header Host $host;
        proxy_set_header X-Forwarded-Proto $scheme;

        # The chat endpoint streams server-sent events. Buffering them delays
        # every progress event until the turn completes.
        proxy_buffering off;
        proxy_read_timeout 3600s;
    }
}

server {
    listen 80;
    server_name staging.example.com;
    return 301 https://$host$request_uri;
}
```

Once the site is on HTTPS, add that origin to the assistant's allowed origins if
you also call it directly; the SPA itself never needs it, because it always calls
the same origin it was served from.

## 7. Monitoring

Both services expose health and metrics endpoints; neither is publicly routed.

| Signal | Endpoint | Notes |
| --- | --- | --- |
| Spring Boot health | `http://backend:9090/api/actuator/health` (compose network) | Authenticated, so scrape it with a service account or from inside the network |
| Assistant liveness / readiness | `http://127.0.0.1:18080/health/live`, `http://127.0.0.1:18080/health/ready` | Readiness covers configuration and the assistant's own database |
| Assistant metrics | `http://127.0.0.1:18080/metrics` | Prometheus text; request counts, latency histograms, chat outcomes, tokens and cost |

A Prometheus scrape config for the assistant:

```yaml
scrape_configs:
  - job_name: expense-ai
    metrics_path: /metrics
    static_configs:
      - targets: ["host.docker.internal:18080"]
```

Alert on at least: `/health/ready` returning not-ready, a rising
`expense_ai_chat_turns_total{outcome="error:*"}` rate, and p95 turn latency. The
metric names, labels and cost counters are documented in
`expense-ai/docs/observability.md`; the retention, deletion and incident
procedures are in `expense-ai/docs/operations.md`.

## 8. Updating and rolling back

```bash
git pull
docker compose -f compose.staging.yaml --env-file .env.staging up --build -d
```

Compose recreates only the services whose image or configuration changed. To
revert, check out the previous commit and run the same command.

A bad migration is rolled back with Alembic inside the assistant container:

```bash
docker compose -f compose.staging.yaml exec expense-ai alembic downgrade -1
```

The financial schema is not managed by migrations in this stack: with
`JPA_DDL_AUTO=update` Hibernate reconciles it on startup. Take a database dump
before upgrading if the data matters:

```bash
docker compose -f compose.staging.yaml exec -T financial-db \
  pg_dump -U "$FINANCIAL_DB_USERNAME" "$FINANCIAL_DB_NAME" > financial-backup.sql
```

## 9. Known limitations

- Single host, single replica. Rate limiting and conversation state are
  in-process/in-database, so scaling the assistant horizontally needs a shared
  limiter first — see `expense-ai/docs/phase-4-hardening.md`.
- TLS, managed secrets and a log/metrics pipeline are configured outside this
  stack on purpose; the compose file is not a production topology by itself.
- Assistant answers stream as a single `token` event because the provider
  adapters are non-streaming; the UI handles incremental tokens already, so
  enabling provider streaming later needs no frontend change.
- `frontend/nginx.conf` resolves the upstream names `backend` and `expense-ai` at
  startup, so the service names in `compose.staging.yaml` are part of the contract.
