"""API key authentication for every route except the public ones.

A request is authenticated by one of:
- `Authorization: Bearer <key>`, for programs;
- HTTP Basic with any user name and the key as password, so a browser can open `/docs`.
"""

import base64
import binascii
import secrets

from fastapi import HTTPException, Request, status
from fastapi.security.utils import get_authorization_scheme_param
from pydantic import SecretStr

PUBLIC_PATHS = frozenset({"/health"})
CHALLENGE = 'Basic realm="Cordel Vivo", Bearer'


def _key_from_header(authorization: str | None) -> str | None:
    scheme, credentials = get_authorization_scheme_param(authorization)
    scheme = scheme.lower()
    if scheme == "bearer":
        return credentials or None
    if scheme == "basic":
        try:
            decoded = base64.b64decode(credentials, validate=True).decode("utf-8")
        except (binascii.Error, UnicodeDecodeError):
            return None
        _, separator, password = decoded.partition(":")
        return password if separator and password else None
    return None


def is_valid_key(candidate: str, keys: tuple[SecretStr, ...]) -> bool:
    """Compare against every key in constant time, without stopping at the first match."""
    given = candidate.encode("utf-8")
    matches = [
        secrets.compare_digest(given, key.get_secret_value().encode("utf-8")) for key in keys
    ]
    return any(matches)


def require_api_key(request: Request) -> None:
    """FastAPI dependency applied to the whole application; skips only PUBLIC_PATHS."""
    if request.url.path in PUBLIC_PATHS:
        return
    keys: tuple[SecretStr, ...] = request.app.state.api_keys
    candidate = _key_from_header(request.headers.get("Authorization"))
    if candidate is None or not is_valid_key(candidate, keys):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Missing or invalid API key",
            headers={"WWW-Authenticate": CHALLENGE},
        )
