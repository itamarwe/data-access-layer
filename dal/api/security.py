"""Bearer authentication and optimistic-concurrency headers."""

from __future__ import annotations

import hmac
from typing import Annotated

from fastapi import Header, HTTPException, Request, Security
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer

bearer = HTTPBearer(auto_error=False)


def authentication_error(header: str | None, expected: str | None) -> tuple[int, str] | None:
    if expected is None:
        return None
    scheme, separator, supplied = (header or "").partition(" ")
    if not separator or scheme.lower() != "bearer":
        return 401, "Bearer authentication is required"
    if not hmac.compare_digest(supplied, expected):
        return 403, "Authentication token is invalid"
    return None


async def authorize(
    request: Request,
    credentials: Annotated[HTTPAuthorizationCredentials | None, Security(bearer)],
) -> None:
    expected = request.app.state.config.auth_token
    header = None if credentials is None else f"{credentials.scheme} {credentials.credentials}"
    error = authentication_error(header, expected)
    if error:
        raise HTTPException(*error)


def expected_revision(
    value: Annotated[
        str,
        Header(
            alias="If-Match",
            description="Current sha256 repository revision; every mutation requires it.",
        ),
    ],
) -> str:
    return value[1:-1] if len(value) > 1 and value.startswith('"') and value.endswith('"') else value
