"""Shared fixtures. Unit tests need no network and no database."""

from __future__ import annotations

import pytest
from pydantic import SecretStr

from app.config import Settings

TEST_JWT_SECRET = "unit-test-signing-secret-" + "x" * 32  # test only, never a real secret


@pytest.fixture
def settings() -> Settings:
    # _env_file=None: never read a developer's local .env during tests.
    return Settings(
        _env_file=None,  # type: ignore[call-arg]
        jwt_secret=SecretStr(TEST_JWT_SECRET),
        typesafe_api_key=SecretStr("unit-test-typesafe-key"),
        anthropic_api_key=SecretStr("unit-test-anthropic-key"),
        database_url=SecretStr("postgresql+psycopg://unused:unused@localhost:1/unused"),
        analytics_database_url=SecretStr("postgresql+psycopg://unused:unused@localhost:1/unused"),
        rate_limit_per_minute=1000,
        max_date_span_days=366,
        jev_scope_min_confidence=0.75,
        jev_tool_min_confidence=0.75,
        jev_risk_block_threshold=0.5,
    )
