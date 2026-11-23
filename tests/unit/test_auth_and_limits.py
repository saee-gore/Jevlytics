"""JWT verification, configuration gates, and the rate limiter. Pure logic, no database."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta

import jwt
import pytest
from pydantic import SecretStr

from app.auth.jwt import AuthError, decode_token, issue_token
from app.config import Settings
from app.orchestration.rate_limit import SlidingWindowRateLimiter


def _token(settings: Settings, **overrides: object) -> str:
    return issue_token(
        settings=settings, user_id="u-1", merchant_id="merchant_001", role="ANALYST", **overrides
    )  # type: ignore[arg-type]


def test_round_trip_yields_claims(settings: Settings) -> None:
    claims = decode_token(_token(settings), settings)
    assert (claims.subject, claims.merchant_id, claims.role) == ("u-1", "merchant_001", "ANALYST")


def test_expired_token_is_rejected(settings: Settings) -> None:
    token = _token(settings, ttl_minutes=-5)
    with pytest.raises(AuthError):
        decode_token(token, settings)


def test_wrong_audience_and_issuer_are_rejected(settings: Settings) -> None:
    bad_aud = jwt.encode(
        {
            "sub": "u",
            "merchant_id": "m",
            "role": "ANALYST",
            "iss": settings.jwt_issuer,
            "aud": "other",
            "iat": datetime.now(UTC),
            "nbf": datetime.now(UTC),
            "exp": datetime.now(UTC) + timedelta(minutes=5),
        },
        settings.jwt_secret.get_secret_value(),  # type: ignore[union-attr]
        algorithm="HS256",
    )
    with pytest.raises(AuthError):
        decode_token(bad_aud, settings)
    bad_iss = jwt.encode(
        {
            "sub": "u",
            "merchant_id": "m",
            "role": "ANALYST",
            "iss": "evil",
            "aud": settings.jwt_audience,
            "iat": datetime.now(UTC),
            "nbf": datetime.now(UTC),
            "exp": datetime.now(UTC) + timedelta(minutes=5),
        },
        settings.jwt_secret.get_secret_value(),  # type: ignore[union-attr]
        algorithm="HS256",
    )
    with pytest.raises(AuthError):
        decode_token(bad_iss, settings)


def test_tampered_token_is_rejected(settings: Settings) -> None:
    token = _token(settings)
    header, payload, signature = token.split(".")
    forged_payload = jwt.utils.base64url_encode(
        b'{"sub":"u-1","merchant_id":"merchant_002","role":"ANALYST","iss":"merchant-analytics",'
        b'"aud":"merchant-analytics-api","iat":1,"nbf":1,"exp":9999999999}'
    ).decode()
    with pytest.raises(AuthError):
        decode_token(f"{header}.{forged_payload}.{signature}", settings)


def test_alg_none_is_rejected(settings: Settings) -> None:
    unsigned = jwt.encode(
        {
            "sub": "u",
            "merchant_id": "m",
            "role": "ANALYST",
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
            "iat": datetime.now(UTC),
            "nbf": datetime.now(UTC),
            "exp": datetime.now(UTC) + timedelta(minutes=5),
        },
        key="",
        algorithm="none",
    )
    with pytest.raises(AuthError):
        decode_token(unsigned, settings)


def test_missing_required_claim_is_rejected(settings: Settings) -> None:
    no_merchant = jwt.encode(
        {
            "sub": "u",
            "role": "ANALYST",
            "iss": settings.jwt_issuer,
            "aud": settings.jwt_audience,
            "iat": datetime.now(UTC),
            "nbf": datetime.now(UTC),
            "exp": datetime.now(UTC) + timedelta(minutes=5),
        },
        settings.jwt_secret.get_secret_value(),  # type: ignore[union-attr]
        algorithm="HS256",
    )
    with pytest.raises(AuthError):
        decode_token(no_merchant, settings)


def test_auth_refuses_short_secret(settings: Settings) -> None:
    weak = settings.model_copy(update={"jwt_secret": SecretStr("short")})
    assert weak.auth_configured is False
    with pytest.raises(AuthError):
        decode_token("a.b.c", weak)


def test_jev_and_llm_report_unconfigured_when_keys_empty(settings: Settings) -> None:
    empty = settings.model_copy(update={"typesafe_api_key": SecretStr(""), "anthropic_api_key": None})
    assert empty.jev_configured is False
    assert empty.llm_configured is False


def test_rate_limiter_blocks_then_recovers_after_window() -> None:
    clock = {"now": 1000.0}
    limiter = SlidingWindowRateLimiter(limit_per_minute=3, clock=lambda: clock["now"])
    assert [limiter.allow("u") for _ in range(4)] == [True, True, True, False]
    assert limiter.allow("other-user") is True  # limits are per user
    clock["now"] += 61
    assert limiter.allow("u") is True


def test_rate_limiter_rejects_nonsense_limit() -> None:
    with pytest.raises(ValueError):
        SlidingWindowRateLimiter(limit_per_minute=0)
