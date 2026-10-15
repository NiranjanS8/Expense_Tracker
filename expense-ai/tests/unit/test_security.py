from __future__ import annotations

import pytest

from app.core.errors import UnauthenticatedError
from app.core.security import AccessToken, extract_access_token


def test_access_token_never_reveals_itself_in_repr_or_str() -> None:
    token = AccessToken("super-secret-token")

    assert "super-secret-token" not in repr(token)
    assert "super-secret-token" not in str(token)
    assert token.reveal() == "super-secret-token"


def test_fingerprint_is_stable_and_not_the_token() -> None:
    token = AccessToken("super-secret-token")

    assert token.fingerprint() == AccessToken("super-secret-token").fingerprint()
    assert token.fingerprint() != AccessToken("other-token").fingerprint()
    assert "super-secret-token" not in token.fingerprint()


async def test_extract_access_token_accepts_bearer_header() -> None:
    token = await extract_access_token("Bearer abc.def.ghi")

    assert token.reveal() == "abc.def.ghi"


@pytest.mark.parametrize("header", [None, "", "   ", "Basic abc", "Bearer", "Bearer   "])
async def test_extract_access_token_rejects_missing_or_malformed_headers(header: str | None) -> None:
    with pytest.raises(UnauthenticatedError):
        await extract_access_token(header)
