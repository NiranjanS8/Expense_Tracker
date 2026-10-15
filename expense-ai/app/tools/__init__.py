"""Read-only tools over the verified Expense Tracker API.

Every tool validates its arguments, forwards the caller's bearer token to Spring
Boot, and returns a typed result or a typed, client-safe error. Tools never touch
the financial database and never accept an identity argument.
"""

from __future__ import annotations

from app.tools.registry import ToolDefinition, ToolRegistry, build_tool_registry

__all__ = ["ToolDefinition", "ToolRegistry", "build_tool_registry"]
