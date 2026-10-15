# Phase 0 — Repository Discovery Report

Status: **Reviewed. Key architectural decisions approved; implementation not yet started. No implementation code has been written.**

Approved decisions (project owner, Phase 0 review):
- **Authentication:** Option A — FastAPI validates the forwarded token by calling `GET /users/me`; the JWT signing secret is never shared with the AI service.
- **Aggregate endpoint:** approved — add the single read-only `GET /api/expenses/summary` to Spring Boot.
- **Phase 1 persistence:** stateless — no AI-owned database in Phase 1; PostgreSQL + Alembic arrive in Phase 3 when conversation persistence is needed.
Scope: Inspect the existing Expense Tracker Spring Boot application to establish the verified API contract, authentication model, data/aggregation gaps, and the recommended architecture for the Python + FastAPI + LangGraph assistant.

Evidence base: source files read directly from `src/main/java/com/expensetracker/**`, `src/test/java/**`, `pom.xml`, `src/main/resources/application.properties`, `src/test/resources/application.properties`, and `frontend/src/**`. Statements below are marked **[verified]** when read from source and **[open]** when they could not be confirmed.

---

## 1. Current architecture

- **Shape:** Modular monolith, package-by-feature under `com.expensetracker`. **[verified]**
- **Runtime:** Java 21, Spring Boot 4.0.0, Spring Web, Spring Data JPA/Hibernate, Spring Security, Spring Validation, Spring Mail, Actuator, Springdoc OpenAPI 3.0.1, JJWT 0.12.6, OpenPDF 2.0.3, Lombok. **[verified — `pom.xml`]**
- **Server:** port `9090`, servlet context path `/api` (`server.servlet.context-path=/api`). All controllers are declared *without* the `/api` prefix; the context path supplies it. **[verified]**
- **Persistence:** PostgreSQL at runtime; H2 (PostgreSQL compatibility mode) for tests with `ddl-auto=create-drop`. Runtime `ddl-auto=validate` by default. `hibernate.jdbc.time_zone=UTC`. **[verified]**
- **No** Flyway/Liquibase migrations, **no** Docker, **no** CI/CD, **no** production profile, **no** `Dockerfile` or `compose.yaml`. **[verified — absent; `.github/` not present, no migration files]**
- **Frontend:** React 19 + Vite 7 demo client. Dev server proxies `/api` → `http://localhost:9090`. Token + user + month persisted in `localStorage` (no refresh, no expiry handling beyond message sniffing). **[verified]**
- **Patterns:** DTO-first controllers, command/query service separation for expenses/budgets/goals, lightweight Spring domain events, scheduled jobs with DB-backed locks (`JobLockService`), per-request correlation IDs, Micrometer metrics. **[verified]**
- **Existing tests:** 10 test classes (5 integration, 5 unit/service). MockMvc + H2 + Spring Security Test. `<TEST NAME>` suites per `PROJECT_CONTEXT.md`. **[verified]**

---

## 2. API inventory (verified)

All paths below are relative to the context path; externally they are prefixed with `/api`. All endpoints except `POST /api/auth/*` and the Swagger/OpenAPI routes require a valid bearer token. **[verified — `SecurityConfig`]**

### 2.1 Authentication (`/auth`) — public, `@SecurityRequirements` in OpenAPI

| Method | Path | Body | Success | Notes |
|---|---|---|---|---|
| POST | `/auth/register` | `RegisterRequest{fullName,email,password}` | `201` `AuthResponse` | IP rate limit: 3/hour. Duplicate email → `400`. |
| POST | `/auth/login` | `LoginRequest{email,password}` | `200` `AuthResponse` | IP rate limit: 5/minute. Bad credentials → `401`. |

`AuthResponse = { accessToken: string, tokenType: "Bearer", user: UserProfileResponse }`
`UserProfileResponse = { id: Long, fullName: string, email: string, role: "USER"|... }` **[verified]**

### 2.2 User

| Method | Path | Response |
|---|---|---|
| GET | `/users/me` | `UserProfileResponse` |

### 2.3 Categories

| Method | Path | Response |
|---|---|---|
| GET | `/categories` | `List<CategoryResponse{id,name,systemDefined}>` — system-defined **plus** the caller's own. Not paginated. |
| POST | `/categories` | `201` `CategoryResponse` |

### 2.4 Expenses (`/expenses`)

| Method | Path | Notes |
|---|---|---|
| GET | `/expenses` | Paginated list; see filters below. |
| GET | `/expenses/{expenseId}` | `ExpenseResponse`; owner-scoped (`findByIdAndUserId`). |
| POST | `/expenses` | `201`. |
| PUT | `/expenses/{expenseId}` | Owner-scoped. |
| DELETE | `/expenses/{expenseId}` | `204`. Owner-scoped. |

GET query parameters: `page` (default 0, ≥0), `size` (default 10, **1..100**), `sortBy` (`expenseDate`|`amount`|`createdAt`), `sortDir` (`asc`|`desc`), `search` (free text; case-insensitive `LIKE` over description **and** category name), `categoryId`, `startDate`, `endDate` (ISO `yyyy-MM-dd`), `minAmount`, `maxAmount`. **[verified]**

Paged envelope: `PagedResponse<T> = { content: T[], page, size, totalElements, totalPages, first, last, empty }`. **[verified]**

`ExpenseResponse = { id, categoryId, categoryName, amount, expenseDate (yyyy-MM-dd), description, paymentMethod }`. **[verified]**

Rejections: `startDate > endDate` or `minAmount > maxAmount` → `400 BadRequest`. Unknown `sortBy`/`sortDir` → `400`.

### 2.5 Budgets (`/budgets`)

| Method | Path | Response |
|---|---|---|
| POST | `/budgets` | `201` `BudgetSummaryResponse` |
| PUT | `/budgets/{budgetMonth}` | `BudgetSummaryResponse` |
| GET | `/budgets/{budgetMonth}` | `BudgetSummaryResponse`; `404` if none |
| GET | `/budgets/current` | `BudgetSummaryResponse`; **`200` with empty placeholder if none** |
| GET | `/budgets?budgetMonth=&year=` | `List<BudgetSummaryResponse>`; supplying both → `400` |

`budgetMonth` is `yyyy-MM`, constrained to `2000-01`..`2100-12`. `BudgetSummaryResponse = { id, budgetAmount, budgetMonth, spentAmount, remainingAmount, overBudgetAmount, usagePercentage, exceeded, hasRemainingBudget, status, alertLevel, alertMessage, triggeredThresholds[] }` where `status ∈ {ON_TRACK, WARNING, CRITICAL, EXCEEDED}`. Thresholds default `80,90,100`. **[verified]**

### 2.6 Goals (`/goals`)

| Method | Path | Response |
|---|---|---|
| GET | `/goals` | `List<GoalResponse>` ordered by target date |
| GET | `/goals/{goalId}` | `404` if not owned |
| POST | `/goals` | `201` |
| PUT | `/goals/{goalId}` | |
| DELETE | `/goals/{goalId}` | `204` |

`GoalResponse = { id, name, targetAmount, currentAmount, remainingAmount, progressPercentage, requiredMonthlyContribution, targetDate, status }`, `status ∈ {ON_TRACK, AT_RISK, COMPLETED, OVERDUE}`. **[verified]**

### 2.7 Dashboard (`/dashboard`)

| Method | Query | Response |
|---|---|---|
| GET | `/dashboard/summary?month=yyyy-MM&recentLimit=5` | `{ month, monthlyTotal, transactionCount, recentTransactions: ExpenseResponse[] }` |
| GET | `/dashboard/categories?month=yyyy-MM` | `List<{categoryId, categoryName, totalAmount}>` |
| GET | `/dashboard/trends?months=6` | `List<{month, totalAmount}>` |
| GET | `/dashboard/charts?month=&months=` | `{ pieChart[], barChart[], lineChart[] }` |

`month` defaults to the current month. `recentLimit` 1..20, `months` 1..24. Trends start from `YearMonth.now().minusMonths(months-1)` — **the window always ends at the current month**. **[verified]**

### 2.8 Insights (`/insights`)

| Method | Query | Response |
|---|---|---|
| GET | `/insights/summary?month=yyyy-MM` | `InsightsSummaryResponse` |

`InsightsSummaryResponse = { month, currentMonthTotal, previousMonthTotal, absoluteChange, percentageChange, averageDailySpend, topCategory, topCategorySharePercentage, largestExpense, insights: InsightItemResponse[] }` and `InsightItemResponse = { type, title, message }`. Future months → `400`. Comparison is **current month vs the single immediately preceding month only**. **[verified]**

### 2.9 Recurring expenses (`/recurring-expenses`)

| Method | Path | Notes |
|---|---|---|
| GET | `/recurring-expenses` | `List<RecurringExpenseResponse>` |
| POST | `/recurring-expenses` | `201` |
| PUT | `/recurring-expenses/{id}` | |
| PATCH | `/recurring-expenses/{id}/status` | Body `{active:boolean}` |
| POST | `/recurring-expenses/generate?runDate=` | Rate-limited 10/hour/user; **mutating** |

`RecurringExpenseResponse = { id, categoryId, categoryName, amount, startDate, nextExecutionDate, description, paymentMethod, frequency, active }`, `frequency ∈ {WEEKLY, MONTHLY}`. **[verified]**

### 2.10 Smart category rules (`/smart-category-rules`)

GET (list), POST (`201`), PUT `/{ruleId}`, DELETE `/{ruleId}` (`204`). Keyword → category mapping. **[verified]**

### 2.11 Exports (`/exports`)

| Method | Path | Notes |
|---|---|---|
| POST | `/exports/jobs` | `202`, body `{type:"CSV"|"PDF", sortBy, sortDir, search, categoryId, startDate, endDate, minAmount, maxAmount}`; rate-limited 5/10min/user; **mutating** |
| GET | `/exports/jobs` | `List<ExpenseExportJobResponse>` (caller's only) |
| GET | `/exports/jobs/{jobId}` | Owner-scoped; `404` otherwise |
| GET | `/exports/jobs/{jobId}/download` | Binary; owner-scoped |
| GET | `/exports/expenses/csv` | **`410 Gone`** |
| GET | `/exports/expenses/pdf` | **`410 Gone`** |

`ExpenseExportJobResponse = { id, type, status, fileName, contentType, errorMessage, downloadReady, createdAt, startedAt, completedAt }`. **[verified]**

### 2.12 Email reports (`/email-reports`)

| Method | Path | Notes |
|---|---|---|
| GET | `/email-reports/preference` | `{id, email, enabled}` |
| PUT | `/email-reports/preference` | |
| POST | `/email-reports/send?month=yyyy-MM` | Rate-limited 2/hour/user; **sends real mail if configured** |

### 2.13 Actuator

`management.endpoints.web.exposure.include=health,info,metrics` **but** `SecurityConfig` only permits `/auth/**` and Swagger routes. Therefore `/api/actuator/**` requires authentication and returns **`403`** without a token. Actuator is **not** publicly reachable. **[verified by config + security rule]**

### 2.14 Error format

`ApiErrorResponse = { timestamp (Instant), status (int), error (reason phrase), message, path, details: string[] }`. **[verified]**

| Condition | Status | Body |
|---|---|---|
| Bean validation | `400` | `message="Validation failed"`, populated `details` |
| Domain bad request | `400` | domain message |
| Not found / not owned | `404` | "…not found" |
| Bad credentials | `401` | "Invalid email or password" |
| Rate limited | `429` | message + `Retry-After` header |
| Unhandled | `500` | "An unexpected error occurred" |
| **Missing / invalid / expired token** | **`403`** | **Spring's default `Http403ForbiddenEntryPoint` — no JSON body** |

The `403`-for-unauthenticated behavior is **confirmed by `AuthSecurityIntegrationTest.protectedEndpointShouldRejectMissingToken`**, which asserts `isForbidden()`. This is the single most important contract subtlety for the AI service.

---

## 3. Authentication implementation (verified)

- **Algorithm:** HMAC (HS256) via JJWT; signing/verifying key derived from `app.security.jwt.secret` (`Decoders.BASE64.decode`, falling back to raw UTF-8 bytes if not valid Base64). **[verified — `JwtService`]**
- **Claims actually issued:** `sub` = **user email (lowercased)**, `iat`, `exp`. **No `iss`, no `aud`, no `jti`, no role claim, no user-id claim.** `generateToken` passes an empty `Map.of()` for extra claims. **[verified — `AuthService`, `JwtService`]**
- **Expiration:** fixed `86400000 ms` = **24 hours** from `app.security.jwt.expiration`. No refresh token, no rotation, no revocation/denylist. **[verified]**
- **Verification in Java:** signature → expiry → `sub` must resolve to an existing user via `CustomUserDetailsService` (DB lookup on every request) and must equal `userDetails.getUsername()`. A token for a deleted user therefore fails. **[verified — `JwtAuthenticationFilter`]**
- **Identity propagation:** controllers receive `@AuthenticationPrincipal User user`; ownership is enforced from `user.getId()` inside services/repositories (`findByIdAndUserId`, `findAllByUserId…`). **No endpoint accepts a caller-supplied user id.** **[verified]**
- **Secret default:** `app.security.jwt.secret=${JWT_SECRET:}` — empty default. With an empty secret, signing would fail (`WeakKeyException`). Real secret lives in the gitignored `.env`. **[verified — properties + `.gitignore`; secret value not read]**
- **`/auth/**` is `permitAll`; everything else `authenticated()`; CSRF disabled; stateless sessions; no custom `AuthenticationEntryPoint`.** **[verified]**

### 3.1 Rate limiting (verified)

Process-local `ConcurrentHashMap` counters (not distributed): login `5/min/IP`, register `3/hour/IP`, export job `5/10min/user`, email send `2/hour/user`, recurring generation `10/hour/user`. **There is no rate limiting on any read endpoint.** Client IP is taken from `X-Forwarded-For` first, else `remoteAddr`. **[verified — `RateLimitService`]**

### 3.2 Correlation and logging (verified)

`RequestCorrelationFilter` runs before the JWT filter. It reads `X-Correlation-Id` from the request (trimmed) or generates a UUID, puts it in MDC, and echoes it on the response header. Log pattern: `%5p [corr:%X{correlationId:-}]`. Logs emit `event=http_request method path status durationMs clientIp`. **No request/response bodies, tokens, or financial payloads are logged by default.** **[verified]**

### 3.3 Date/timezone semantics (verified)

- `expenseDate` is a `LocalDate` with **no timezone**. Month windows are computed with `YearMonth.now()` / `LocalDate.now()` (JVM local clock) and `atDay(1)`/`atEndOfMonth()`. `Hibernate time_zone=UTC` affects timestamp columns only. **[verified — `DashboardService`, `InsightsService`, `GoalQueryService`]**
- Consequence: "this month" means the **backend JVM's local calendar month**, not the user's timezone. The AI service must not invent its own month boundaries; it should defer to these semantics and document the assumption.

---

## 4. Which aggregates already exist vs. which must be composed

**Available as first-class aggregates (use these; do not recompute in Python):**
- Monthly total + transaction count + recent transactions — `/dashboard/summary`. **[verified]**
- Per-category totals for a given month — `/dashboard/categories`. **[verified]**
- Multi-month trends ending at the current month — `/dashboard/trends`. **[verified]**
- Month-over-month comparison, top category + share, largest expense, pre-written narrative insights — `/insights/summary`. **[verified]**
- Budget spend/remaining/usage/status/alert — `/budgets/*`. **[verified]**
- Goal progress/status/required contribution — `/goals`. **[verified]**

**Not available — must be composed or is impossible with current endpoints:**
1. **Sum for an arbitrary date range.** There is no "total matching these filters" endpoint. `sumAmountByUserIdAndExpenseDateBetween` is month-scoped and not exposed generically. `/expenses` returns `totalElements` (a **count**) but never a **sum**. **[verified]**
2. **Sum by category for an arbitrary range.** Category totals exist only per month (`/dashboard/categories`).
3. **Comparison of two arbitrary periods.** `/insights/summary` only does N vs N-1 month. "This month vs the same month last year" is not supported.
4. **Historical trend windows.** `/dashboard/trends` always ends at the current month; you cannot request a window ending in the past.
5. **Week/quarter/last-30-days/rolling periods.** Only `YearMonth` and explicit `yyyy-MM-dd` ranges (on the list endpoint) exist.
6. **Expenses sorted by amount across the full set without paging.** "Top 5 largest this month" must page `/expenses?sortBy=amount&sortDir=desc&startDate=…&endDate=…` (page size ≤ 100). `/insights/summary` gives only the single largest.
7. **Category lookup by name.** Only "list all categories" + client-side matching; no name→id endpoint.
8. **Expense totals/counts per category within the list response.** Not present.

Composition cost note: to compute a sum over an arbitrary range with current endpoints, the AI service must page `/expenses` at ≤100 rows and add amounts in Python. This is acceptable for small data but is unbounded in request count and is exactly the kind of "do not fabricate/stale" risk the plan warns about. **This is the primary driver for a minimal new Java aggregate endpoint (see §6).**

---

## 5. Recommended AI-service → Spring Boot authentication flow

### Option A (recommended, minimal risk): token introspection via `/users/me`, no secret sharing

1. Frontend sends its existing `Authorization: Bearer <token>` to FastAPI.
2. FastAPI does **not** verify the signature locally. It calls `GET /api/users/me` with the forwarded token. Success ⇒ the token is valid *per the authority*, and the response yields the **trusted** `userId` and `email`.
3. FastAPI caches the `(token → userId)` binding in memory keyed by a **hash** of the token for a short TTL (e.g. 60s) to avoid one introspection call per hop, then calls the target endpoint with the same forwarded token.
4. Spring Boot independently re-validates the token on every call and enforces ownership. Identity is never taken from chat text or tool arguments.

Pros: no JWT secret leaves the Java service; no audience/issuer assumptions; a deleted or invalidated user is rejected immediately by the authority; zero Java changes. Cons: one extra HTTP round-trip (mitigated by short-lived caching); FastAPI must handle the `403`/empty-body case.

### Option B (alternative): local signature verification with the shared secret

FastAPI verifies HS256 + `exp` locally using a verification-only copy of `JWT_SECRET`, takes `sub` (email) as identity, and still resolves `userId` via `/users/me` (since no id claim exists). Pros: fewer round-trips. Cons: the signing secret is duplicated into a second service and, because the token has **no `aud`/`iss`**, it is valid for any service sharing the secret — a real blast-radius increase. Not recommended for the first release.

### Flow requirements (both options)

- Never trust `userId` from chat text, request bodies, or tool arguments.
- Never place bearer tokens in prompts, model messages, graph state, or logs; redact `Authorization` in all logging.
- Validate expiry, signature (Option B), and reject missing/malformed tokens as `401` at the FastAPI boundary even though Spring returns `403`.
- Propagate `X-Correlation-Id` to every downstream call; generate one if absent.
- Use per-user and per-IP rate limits on chat and a separate budget for model spend.
- Keep an explicit mapping table for upstream status → AI-service status: `403`(no body) ⇒ `401`; `404` ⇒ `404`; `429` ⇒ `429` (+`Retry-After`); `5xx`/timeout ⇒ `503`.
- TLS for all non-local traffic.

---

## 6. Missing APIs and security gaps

### 6.1 Recommended minimal Java change (needs approval)

Add **one** read-only aggregate endpoint to close the largest data gap while keeping Spring Boot as the calculation authority:

```
GET /api/expenses/summary
    ?startDate=&endDate=&categoryId=&minAmount=&maxAmount=&search=
 → { totalAmount, transactionCount, startDate, endDate }
```

- Owner-scoped from `@AuthenticationPrincipal User`; reuses `ExpenseSpecifications` + a new `sum` query.
- Read-only, no behavior change to existing endpoints, testable with the existing MockMvc + H2 setup.
- Optional second endpoint (`GET /api/expenses/by-category`) only if we decide the AI must aggregate out-of-month ranges; otherwise defer.

**Do not** add mutation endpoints for the read-only release. Explicitly deferred to the write phase: create/update expense, budget, goal, recurring rule; export job creation; email send.

### 6.2 Security gaps / risks (verified unless noted)

1. **`403` with an empty body for unauthenticated/invalid/expired tokens.** No `AuthenticationEntryPoint` is configured, so clients cannot distinguish "not logged in" from "forbidden." The AI service must handle this; a Java change adding a JSON `401`/`403` entry point is a plausible later hardening item. **[verified by test]**
2. **No `aud`, no `iss`, no `jti`, no revocation, no refresh.** Logout is client-side only; a stolen token is valid for up to 24h. **[verified]**
3. **Single shared HS256 secret.** Any second service that verifies tokens becomes an alternate trust root. Option A avoids this. **[verified]**
4. **Actuator `health`/`info`/`metrics` are reachable by any authenticated user** (path-based rules only exclude `/auth/**`). Minor information exposure. **[verified]**
5. **Rate limiting is process-local and does not cover read endpoints**, so the AI service can generate unbounded read traffic without hitting a limiter. Enforcement must live in the AI service. **[verified]**
6. **No CORS configuration is defined.** Local dev depends on the Vite proxy. The browser-based chat client will need an explicit CORS decision at the AI service (and possibly on the Java side if called directly). **[verified absent]**
7. `search` uses `criteriaBuilder.like` with a bound parameter → parameterized, **not** injectable. Problematic values are only the wildcards `%`/`_` (mild). **[verified]**
8. Free-text `description` (up to 255 chars) is returned in `ExpenseResponse`. Because the AI composes answers from these rows, descriptions are a PII/prompt-injection surface: they must be treated as untrusted data, not instructions, and must not be logged by default. **[verified field; handling is our design responsibility]**
9. **`app.security.jwt.secret` defaults to empty**; failure mode is a runtime signing error rather than a startup validation. **[verified default; exact startup behavior [open]]**

---

## 7. Proposed Python service structure and dependencies

Service lives in a new sibling directory `expense-ai/` at the repository root (mirrors `plan.md` §16). Managed with **uv** (`pyproject.toml` + `uv.lock`).

```
expense-ai/
├── app/
│   ├── main.py
│   ├── api/v1/{chat.py, conversations.py, health.py}
│   ├── core/{config.py, security.py, logging.py, errors.py}
│   ├── identity/{token_verification.py, user_context.py}
│   ├── agent/{graph.py, state.py, nodes.py, routing.py, policies.py, prompts/}
│   ├── tools/{registry.py, expenses.py, budgets.py, goals.py, recurring.py, insights.py}
│   ├── integrations/{expense_tracker_client.py, model_provider.py}
│   ├── conversations/{service.py, repository.py, models.py}
│   ├── observability/
│   └── audit/
├── migrations/            # Alembic, only if AI-owned tables land in Phase 1
├── tests/{unit, integration, security, agent_eval}
├── evals/datasets/
├── pyproject.toml
├── uv.lock
├── .env.example
└── README.md
```

**Initial dependencies (Phase 1 only):** `fastapi`, `uvicorn[standard]`, `pydantic`, `pydantic-settings`, `httpx`, `structlog` (or stdlib JSON logging), `python-jose[cryptography]`/`pyjwt` *(Option B only)*, `pytest`, `pytest-asyncio`, `respx` (HTTP mocking), `ruff`, `mypy`.

**Deferred to later phases:** `langgraph`, provider adapter (`langchain-*` or provider SDK), `sqlalchemy`, `alembic`, `asyncpg`/`psycopg`, `redis`, OpenTelemetry SDK. Persistence (`sqlalchemy`/`alembic`) should only be added in Phase 1 **if** we commit to AI-owned tables immediately; otherwise start stateless and add in Phase 3.

---

## 8. Exact files to create / modify in Phase 1 (proposed)

**Create (all new; no existing file touched):**
- `expense-ai/pyproject.toml`, `expense-ai/uv.lock` — uv-managed project + lockfile.
- `expense-ai/.env.example` — placeholder values only, no secrets.
- `expense-ai/.gitignore` — ignore `.venv/`, `.env`, caches.
- `expense-ai/README.md` — run/test instructions.
- `expense-ai/app/main.py` — FastAPI app factory, router mounting, middleware wiring.
- `expense-ai/app/core/config.py` — settings via `pydantic-settings`.
- `expense-ai/app/core/errors.py` — typed errors + stable public error envelope.
- `expense-ai/app/core/logging.py` — structured logging + correlation ID context.
- `expense-ai/app/core/security.py` — bearer extraction, upstream-token holder (never logged).
- `expense-ai/app/identity/user_context.py` — trusted user context resolved from the authority.
- `expense-ai/app/identity/token_verification.py` — Option A introspection client (Option B verifier stub if chosen).
- `expense-ai/app/api/v1/health.py` — `/health/live`, `/health/ready`.
- `expense-ai/app/api/v1/chat.py` — route placeholder with auth + validation, returns typed "not implemented" *(no LLM yet)*.
- `expense-ai/app/api/v1/conversations.py` — owner-scoped route placeholders.
- `expense-ai/app/api/v1/__init__.py`, plus package `__init__.py` files actually used.
- `expense-ai/tests/unit/test_config.py`, `test_errors.py`, `test_user_context.py`.
- `expense-ai/tests/integration/test_health.py`, `test_auth_boundary.py`.

**Modify (minimal, only if the project owner approves the §6.1 endpoint):**
- `src/main/java/com/expensetracker/expense/controller/ExpenseController.java` — add `GET /expenses/summary`.
- `src/main/java/com/expensetracker/expense/service/ExpenseQueryService.java` — add owner-scoped summary method.
- `src/main/java/com/expensetracker/expense/repository/ExpenseRepository.java` — add a `sum`/`count` query over a specification.
- `src/main/java/com/expensetracker/expense/dto/` — new `ExpenseSummaryResponse` record.
- `src/test/java/com/expensetracker/expense/…` — add integration + ownership tests for the new endpoint.
- Root `README.md` / `PROJECT_CONTEXT.md` — document the AI service (docs only).

**Explicitly not touched in Phase 1:** existing security config, auth, JWT, business logic, frontend, DB schema, `.env`.

---

## 9. Open questions and decisions requiring approval

### Resolved
1. **Authentication option:** A — introspection via `/users/me`, no shared secret. ✅
2. **Aggregate endpoint:** approved — add read-only `GET /api/expenses/summary`. ✅
3. **Phase 1 persistence:** stateless; no PostgreSQL/Alembic until Phase 3. ✅

### Still open
4. **Service location & naming:** `expense-ai/` at repo root with uv — confirm the directory name and that the AI service is in-repo rather than a separate repository.
5. **Model provider:** which managed provider/adapter for the first release? (No provider is implied by the repo. Not needed until Phase 3, but it shapes the adapter interface.)
6. **Introspection cache TTL:** with Option A, confirm the short-TTL `hash(token) → userId` cache (proposed 60s).
7. **Frontend integration:** keep the chat UI out of the existing `frontend/` until Phase 5 (plan default) — confirm.
8. **Deterministic-test fixtures:** may local/E2E tests rely on the seeded `demo@expensetracker.com` dataset, or should they register fresh users only? (The real `.env` will never be read.)
9. **`403`-vs-`401`:** normalize the current empty-body `403` in the AI service now (recommended), or also harden Java later with a JSON `401`/`403` entry point?
10. **Summary endpoint shape:** confirm the response fields `{ totalAmount, transactionCount, startDate, endDate }` and that no per-category variant is needed in Phase 1.

---

## 10. Phase 0 acceptance check

- [x] Repository inspected; endpoints, schemas, pagination and error formats inventoried.
- [x] JWT design, claims, expiration, and current-user derivation verified.
- [x] Aggregation endpoints vs. gaps identified.
- [x] Rate limiting, correlation IDs, logging, DB, and deployment state verified.
- [x] Recommended AI→Java authentication flow documented.
- [x] Missing APIs, security gaps, proposed Python structure, and Phase 1 file list documented.
- [x] No implementation code written.
- [x] Project owner reviewed the integration contract and approved the key decisions.
- [ ] **Explicit go-ahead to begin Phase 1 — pending.**
