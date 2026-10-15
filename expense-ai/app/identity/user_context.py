"""Request-scoped trusted user context.

``UserContext`` is assembled from a verified bearer token plus the authoritative
identity returned by Spring Boot. The token is retained only so it can be
forwarded downstream; it is never serialized, logged, or exposed to the model.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import cast

from fastapi import Depends, Request

from app.core.correlation import get_correlation_id
from app.core.security import AccessToken, extract_access_token
from app.identity.introspection import IdentityResolver
from app.integrations.expense_tracker_client import AuthenticatedUser


@dataclass(frozen=True)
class UserContext:
    user: AuthenticatedUser
    token: AccessToken = field(repr=False)
    correlation_id: str | None = None

    def __repr__(self) -> str:
        return f"UserContext(user_id={self.user.user_id}, correlation_id={self.correlation_id})"


def get_identity_resolver(request: Request) -> IdentityResolver:
    return cast(IdentityResolver, request.app.state.identity_resolver)


async def get_user_context(
    request: Request,
    token: AccessToken = Depends(extract_access_token),
) -> UserContext:
    resolver = get_identity_resolver(request)
    correlation_id = get_correlation_id()
    user = await resolver.resolve(token, correlation_id)
    return UserContext(user=user, token=token, correlation_id=correlation_id)
