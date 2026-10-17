# Observability

This service records its own metrics, keeps structured logs free of secrets, and
supports optional trace export. Nothing here requires a metrics server, and trace
export is off unless someone deliberately turns it on.

## Metrics

Counters and histograms are authored in-process (`app/observability/metrics.py`)
and rendered in the Prometheus text format by `GET /metrics`. The endpoint is
**closed by default**; enable it with `METRICS_ENABLED=true` and expose it only on
a trusted network — it is an operational surface, not a public one.

```bash
curl http://localhost:8080/metrics
```

Recording is always on and cheap, so metrics are available the moment the scrape
endpoint is enabled. Labels are drawn from a small, closed set (endpoint names,
tool names, outcomes, providers), never from user identifiers, amounts or
descriptions, so series cardinality cannot grow with traffic.

| Metric | Type | Labels | Meaning |
| --- | --- | --- | --- |
| `expense_ai_http_requests_total` | counter | `method`, `route`, `status` | Requests handled |
| `expense_ai_http_request_duration_seconds` | histogram | `method`, `route` | Request latency |
| `expense_ai_chat_turns_total` | counter | `outcome` | Assistant turns by outcome (`answered`, `no_data`, `tool_error`, `model_error`, `cancelled`, `error:<code>`) |
| `expense_ai_chat_turn_duration_seconds` | histogram | — | Turn latency, including time spent streaming |
| `expense_ai_tool_calls_total` | counter | `tool`, `outcome` | Upstream tool calls |
| `expense_ai_tool_call_duration_seconds` | histogram | `tool` | Tool call latency |
| `expense_ai_model_calls_total` | counter | `provider`, `node`, `outcome` | Model calls |
| `expense_ai_model_call_duration_seconds` | histogram | `provider`, `node` | Model call latency |
| `expense_ai_model_tokens_total` | counter | `provider`, `kind` (`prompt`/`completion`) | Tokens consumed |
| `expense_ai_model_cost_usd_total` | counter | `provider`, `model` | Estimated cost |
| `expense_ai_rate_limit_rejections_total` | counter | `scope` | Requests rejected by a rate limiter |
| `expense_ai_auth_denials_total` | counter | `reason` | Rejected authentication / authorization |

`route` is the matched endpoint name (for example `submit_message`), which is
stable and unique without carrying identifiers.

### Cost estimates

`app/observability/cost.py` holds a small table of indicative list prices and
converts token usage into an estimated USD cost. It is a **visibility aid, not a
billing record**: an unknown model contributes `0.0` rather than a guess, and the
table must be updated when a provider changes its pricing.

## Tracing (optional)

Tracing is **off by default**. It exports prompts, tool results and model metadata
to a LangSmith-compatible backend; for this service that means the user's question
and the financial figures the tools returned. Treat enabling it as a privacy
decision, not a convenience:

- Enable it for development, or
- Point `LANGSMITH_ENDPOINT` at a **self-hosted** instance your organisation has
  approved for that data.

| Variable | Purpose |
| --- | --- |
| `LANGSMITH_TRACING` | `true` enables export; anything else leaves it off |
| `LANGSMITH_API_KEY` | Credential for the backend; required when tracing is on |
| `LANGSMITH_PROJECT` | Project/run grouping name |
| `LANGSMITH_ENDPOINT` | Backend URL; set it for a self-hosted instance |

`configure_tracing` translates these typed settings into the environment variables
LangGraph reads, and logging records a warning when tracing is on so it is never
enabled silently. To disable it, set `LANGSMITH_TRACING=false`; the application
does not set the variable in that case.

## Logging and redaction

Logs are structured JSON. `JsonFormatter` redacts known-sensitive keys
(`authorization`, `token`, `api_key`, `password`, `secret`, …) and never includes
prompts, tool payloads or amounts. The bearer token is wrapped so its `repr` is
hidden and only the `UserContext` holds it, never graph state or prompts.

The HTTP client's per-request `INFO` logs are muted (they include query
parameters); the client's own structured events cover the diagnostics worth
keeping.

## Rate limits and cost controls

- A per-user chat limit (`CHAT_RATE_LIMIT_PER_MINUTE`) rejects excess turns with
  `429`, counted in `expense_ai_rate_limit_rejections_total`.
- Request bodies are capped by `MAX_REQUEST_BYTES` (`413`), and messages by length
  at the schema boundary (`422`).
- Per turn, tool calls are bounded by `AGENT_MAX_TOOL_CALLS` and graph steps by
  `AGENT_RECURSION_LIMIT`; model output length is capped by
  `LLM_MAX_OUTPUT_TOKENS`.
- Estimated spend is visible via `expense_ai_model_cost_usd_total`.

The rate limiter is in-process: it must move to a shared store before the service
is scaled horizontally.
