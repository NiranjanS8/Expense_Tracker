"""Canonical binding between an approval and the change it authorises.

The hash covers the owner, the action, the target resource and the arguments.
Every component is included: an approval therefore cannot be replayed by another
user, cannot be reused for a different budget month, and cannot survive an
argument being altered in storage. It is recomputed immediately before execution.
"""

from __future__ import annotations

import hashlib
import json
from collections.abc import Mapping
from typing import Any


def canonical_json(payload: Mapping[str, Any]) -> str:
    """Stable JSON: sorted keys, no insignificant whitespace, UTF-8 preserved."""
    return json.dumps(payload, sort_keys=True, separators=(",", ":"), ensure_ascii=False)


def approval_hash(
    *,
    owner_id: int,
    action: str,
    resource_id: str | None,
    arguments: Mapping[str, Any],
) -> str:
    return hashlib.sha256(
        canonical_json(
            {
                "ownerId": owner_id,
                "action": action,
                "resourceId": resource_id,
                "arguments": dict(arguments),
            }
        ).encode("utf-8")
    ).hexdigest()
