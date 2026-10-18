# Phase 3 — Bounded assistant, persistence, and streaming

Status: implemented and covered by the automated suite (`uv run pytest`,
`ruff`, `mypy`). Read-only; no write capability is enabled.

## What was built

- **Workflow** (`app/agent/`): one `StateGraph` with typed state (`AgentState`)
  and request-scoped context (`AgentContext`). Nodes: `load_context`,
  `classify_intent`, `plan`, `validate_arguments`, `authorize_tool`,
  `execute_tool`, `verify_result`, `compose_draft`, `compose_answer`,
  `persist_and_trace`.
- **Persistence** (`app/conversations/`): SQLAlchemy models, an owner-scoped
  repository, and an Alembic migration (`migrations/versions/0001_…`) for
  `conversations` and `messages`.
- **Streaming** (`app/api/v1/chat.py`, `app/agent/service.py`): typed SSE events
  behind `POST /api/v1/chat`.
- **Conversations API** (`app/api/v1/conversations.py`): owner-scoped list, read,
  delete.

## Boundaries and guarantees

- The token lives only in `AgentContext` (runtime context, `repr=False`); it is
  never placed in graph state, prompts, events, or logs.
- Model output can never widen the tool allowlist, choose a user, or pass an
  identity argument — argument models forbid unknown fields and the registry is
  the only route to an upstream call.
- Tool calls per turn (`AGENT_MAX_TOOL_CALLS`) and graph steps
  (`AGENT_RECURSION_LIMIT`) are bounded.
- Failures degrade to typed, non-fabricating messages. A data question with no
  tool result is refused deterministically rather than answered from memory.
- A conversation id belonging to another user is indistinguishable from a missing
  one (`404`), at the repository boundary and therefore at every endpoint.

## Decisions and trade-offs

- **PostgreSQL is the deployment database; tests use in-memory SQLite.** The same
  SQLAlchemy models and repository run on both. To keep them portable, the schema
  uses dialect-neutral types and timestamps are normalised to UTC on read.
  `AUTO_CREATE_SCHEMA` exists only for tests; Alembic owns the schema in
  deployment.
- **Conversation memory comes from our own tables, not from a LangGraph
  checkpointer.** The graph is invoked statelessly per turn with bounded history
  loaded from `messages`; this is what the plan's "conversation memory is not a
  substitute for current facts" requires, and it avoids a second persistence
  mechanism with no current need.
- **`token` events stream and are provisional.** Each adapter decodes its
  provider's own stream format, reassembling tool-call arguments that arrive in
  fragments. `message_complete.content` stays authoritative: a grounded draft
  that policy later replaces is retracted there, so clients reconcile to that
  value rather than concatenating deltas. Prose from an ungrounded planning call
  is never published, so invented figures cannot appear even transiently.
- **Ambiguity handling for data questions is deterministic.** Because a data
  question may only be answered from tool results, the model cannot emit a
  free-form clarifying question for one; the user instead receives a short
  "rephrase with a period" refusal. A future structured-output path could restore
  model-written clarifications without weakening grounding.
- **Drafts are extracted deterministically, not by the model.** A record request
  is parsed by `app/agent/drafts.py` rather than sent to a provider. This keeps
  the write-side of grounding intact — the assistant cannot propose an amount the
  user never typed — and makes the path work when the provider is down. The cost
  is that unusual phrasings are not understood, which is the safe direction: the
  assistant asks for the amount instead of guessing.

## Open items

- LangGraph PostgreSQL checkpointing, if interrupt/resume is ever needed.
- A retention/cleanup policy for stored conversations (deletion is supported per
  conversation; automation is not).
- A shared rate-limit store before horizontal scaling.
