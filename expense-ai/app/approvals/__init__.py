"""Durable, explicit approval of a proposed write (Phase 6).

Nothing here is reachable unless ``WRITE_OPERATIONS_ENABLED`` is set. Even then
the assistant can only *propose* the write it parsed from the caller's own words;
execution requires a separate, owner-scoped approval request that is single-use.
"""
