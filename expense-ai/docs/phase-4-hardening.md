# Phase 4 — Evaluation and hardening

Status: implemented and covered by the automated suite (`uv run pytest`,
`ruff`, `mypy`). Read-only; no write capability is enabled.

## What was built

- **Evaluation dataset** (`evals/datasets/read_only_assistant.json`): a versioned
  set of representative prompts, each recording the intent the deterministic gate
  must produce, the tool it should drive, the evidence the model must be shown,
  and the answer behaviour expected. The runner (`tests/agent_eval/`) replays each
  case against the app with scripted model steps and a stubbed Spring Boot, so the
  suite is deterministic and offline.
- **Adversarial and security tests** (`tests/security/`): unregistered tools,
  identity and arbitrary-URL arguments, capability-path tool calls, oversized
  input, and assurance that tokens and financial filters never reach logs,
  responses or metrics.
- **Resilience tests** (`tests/integration/test_resilience.py`): upstream timeout
  and transport failure, provider timeout and rate limit, an exhausted step
  budget, and client disconnect.
- **Observability** (`app/observability/`): an in-process metrics registry with a
  Prometheus text endpoint, token and cost counters, and optional trace export.
- **Operational documentation**: `docs/observability.md` and `docs/operations.md`.

## Boundaries and guarantees

- Metrics labels come from a closed set (endpoint names, tool names, outcomes,
  providers); no user identifier, amount or description is ever a label.
- The metrics endpoint is closed unless explicitly enabled, and tracing is off
  unless explicitly enabled with a key.
- Hostile model output cannot widen the allowlist, choose a user, or reach a URL:
  the registry and argument models reject it before any upstream call.
- The HTTP client's per-request logs (which carry query parameters) are muted, so
  financial filters do not leak into logs.
- Failures remain non-fabricating: a data question with no tool result is refused
  rather than answered from memory, and an exhausted step budget degrades to a
  typed event.

## Decisions and trade-offs

- **Metrics are authored in-process rather than through a metrics SDK.** A small
  registry renders the Prometheus format with no extra dependency, which keeps the
  scrape path testable offline and the deployment surface unchanged.
- **Tracing uses LangSmith, off by default.** LangGraph reads its tracing settings
  from the environment and LangSmith already ships with it, so enabling tracing
  costs no new dependency. It is deliberately opt-in because it exports prompts and
  retrieved financial figures to a third party; a self-hosted `LANGSMITH_ENDPOINT`
  is a first-class option. See `docs/observability.md`.
- **The evaluation uses scripted model responses.** Financial correctness depends
  on tool results, not on model prose, so a deterministic suite gives real signal
  on tool selection, grounding and refusal without a model key or network in CI.
  A model-backed evaluation remains a separate, opt-in concern.
- **Cost figures are indicative.** The price table is explicit and small; the
  metric is a visibility aid, not a billing record, and an unknown model counts as
  zero rather than a guess.

## Open items

- A model-backed evaluation run (quality, latency and cost) outside CI.
- A shared rate-limit store before horizontal scaling.
- An automated retention/cleanup policy for stored conversations.
- Load and soak testing against a real environment to set performance targets.
