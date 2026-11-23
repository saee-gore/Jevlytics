"""JWT issuance and verification (HS256 demo configuration).

Verification checks signature, algorithm allowlist, issuer, audience, expiry and required claims.
The token is an identity assertion only. The merchant and role are re-derived from the database by
app/auth/tenant_context.py, so a token cannot grant more than the user record allows.
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import jwt

from app.config import Settings


class AuthError(Exception):
    """Any authentication failure. Clients receive a generic 401; details stay in server logs."""


@dataclass(frozen=True)
class TokenClaims:
    subject: str
    merchant_id: str
    role: str


def issue_token(
    *,
    settings: Settings,
    user_id: str,
    merchant_id: str,
    role: str,
    ttl_minutes: int = 60,
) -> str:
    """Dev/test token issuance. Production identity should come from an external IdP."""
    if not settings.auth_configured or settings.jwt_secret is None:
        raise AuthError("JWT_SECRET is not configured (must be at least 32 characters)")
    now = datetime.now(UTC)
    claims: dict[str, Any] = {
        "sub": user_id,
        "merchant_id": merchant_id,
        "role": role,
        "iss": settings.jwt_issuer,
        "aud": settings.jwt_audience,
        "iat": now,
        "nbf": now,
        "exp": now + timedelta(minutes=ttl_minutes),
        "jti": uuid.uuid4().hex,
    }
    return jwt.encode(claims, settings.jwt_secret.get_secret_value(), algorithm=settings.jwt_algorithm)


def decode_token(token: str, settings: Settings) -> TokenClaims:
    if not settings.auth_configured or settings.jwt_secret is None:
        raise AuthError("authentication is not configured")
    try:
        payload = jwt.decode(
            token,
            settings.jwt_secret.get_secret_value(),
            algorithms=[settings.jwt_algorithm],  # allowlist: never trust the token's own alg header
            audience=settings.jwt_audience,
            issuer=settings.jwt_issuer,
            leeway=settings.jwt_leeway_seconds,
            options={"require": ["exp", "iat", "nbf", "sub", "iss", "aud"]},
        )
    except jwt.PyJWTError as exc:
        raise AuthError("invalid token") from exc

    subject = payload.get("sub")
    merchant_id = payload.get("merchant_id")
    role = payload.get("role")
    if not (
        isinstance(subject, str)
        and subject
        and isinstance(merchant_id, str)
        and merchant_id
        and isinstance(role, str)
        and role
    ):
        raise AuthError("token is missing required claims")
    return TokenClaims(subject=subject, merchant_id=merchant_id, role=role)
