"""Engine and session factories.

Two engines, two roles:
  * app_engine       - DATABASE_URL (merchant_app): tenant reads, audit inserts.
  * analytics_engine - ANALYTICS_DATABASE_URL (analytics_ro): SELECT on aggregate source tables.
"""

from __future__ import annotations

from collections.abc import Iterator
from functools import lru_cache

from sqlalchemy import Engine, create_engine
from sqlalchemy.orm import Session, sessionmaker

from app.config import get_settings


@lru_cache(maxsize=1)
def app_engine() -> Engine:
    return create_engine(
        get_settings().database_url.get_secret_value(),
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
        connect_args={"connect_timeout": 5, "options": "-c statement_timeout=5000"},
    )


@lru_cache(maxsize=1)
def analytics_engine() -> Engine:
    return create_engine(
        get_settings().analytics_database_url.get_secret_value(),
        pool_pre_ping=True,
        pool_size=5,
        max_overflow=5,
        # Per-statement timeout for analytics queries (defence against runaway SQL).
        connect_args={
            "connect_timeout": 5,
            "options": "-c statement_timeout=5000 -c default_transaction_read_only=on",
        },
    )


def app_session() -> Iterator[Session]:
    factory = sessionmaker(bind=app_engine(), expire_on_commit=False)
    with factory() as session:
        yield session


def analytics_session() -> Iterator[Session]:
    factory = sessionmaker(bind=analytics_engine(), expire_on_commit=False)
    with factory() as session:
        yield session
