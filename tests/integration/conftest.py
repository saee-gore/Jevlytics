"""Integration fixtures: a real PostgreSQL database built the same way production is.

Required environment (skipped when absent):
  TEST_ADMIN_DATABASE_URL  superuser or owner URL for a DATABASE WHOSE NAME CONTAINS "test".
                           The database is wiped and rebuilt for each test session.

The fixture runs, in order: alembic upgrade head -> scripts/create_db_roles.sql (via psql) ->
scripts/seed_database.py -> the hand-built known fixture. Application and analytics connections
use the real least-privilege roles that the roles script creates.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from collections.abc import Iterator
from dataclasses import dataclass
from pathlib import Path

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.orm import Session

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))

from tests.fixtures import known_data as kd  # noqa: E402

APP_PASSWORD = "test-app-password"  # test-only credentials, created inside the throwaway test DB
RO_PASSWORD = "test-ro-password"
OWNER_PASSWORD = "test-owner-password"


@dataclass(frozen=True)
class DbEnv:
    admin_url: str
    app_url: str
    analytics_url: str


def _libpq(url: URL) -> str:
    return url.set(drivername="postgresql").render_as_string(hide_password=False)


def _role_url(admin: URL, user: str, password: str) -> str:
    return admin.set(drivername="postgresql+psycopg", username=user, password=password).render_as_string(
        hide_password=False
    )


@pytest.fixture(scope="session")
def db_env() -> Iterator[DbEnv]:
    raw = os.environ.get("TEST_ADMIN_DATABASE_URL", "").strip()
    if not raw:
        pytest.skip("TEST_ADMIN_DATABASE_URL not set; integration tests skipped")
    if shutil.which("psql") is None:
        pytest.skip("psql client not found; needed to apply scripts/create_db_roles.sql")

    admin = make_url(raw)
    if not admin.database or "test" not in admin.database.lower():
        raise RuntimeError("TEST_ADMIN_DATABASE_URL must point at a database whose name contains 'test'")

    env = {
        **os.environ,
        "MIGRATION_DATABASE_URL": admin.set(drivername="postgresql+psycopg").render_as_string(
            hide_password=False
        ),
    }
    admin_engine = create_engine(admin.set(drivername="postgresql+psycopg"))
    with admin_engine.begin() as conn:
        conn.execute(text("DROP SCHEMA IF EXISTS public CASCADE"))
        conn.execute(text("CREATE SCHEMA public"))
    admin_engine.dispose()

    subprocess.run(["alembic", "upgrade", "head"], cwd=ROOT, env=env, check=True, capture_output=True)  # noqa: S603, S607

    subprocess.run(  # noqa: S603
        [
            "psql",
            _libpq(admin),
            "-v",
            "ON_ERROR_STOP=1",
            "-q",
            "-v",
            f"app_password={APP_PASSWORD}",
            "-v",
            f"ro_password={RO_PASSWORD}",
            "-v",
            f"owner_password={OWNER_PASSWORD}",
            "-f",
            str(ROOT / "scripts" / "create_db_roles.sql"),
        ],
        check=True,
        capture_output=True,
    )

    subprocess.run(  # noqa: S603
        [sys.executable, str(ROOT / "scripts" / "seed_database.py")],
        cwd=ROOT,
        env=env,
        check=True,
        capture_output=True,
    )

    _load_known_fixture(admin)

    yield DbEnv(
        admin_url=raw,
        app_url=_role_url(admin, "merchant_app", APP_PASSWORD),
        analytics_url=_role_url(admin, "analytics_ro", RO_PASSWORD),
    )


def _load_known_fixture(admin: URL) -> None:
    engine = create_engine(admin.set(drivername="postgresql+psycopg"))
    with Session(engine) as session, session.begin():
        from app.db.models import Chargeback, Merchant, Settlement, Transaction, User

        for row in kd.MERCHANTS:
            session.merge(Merchant(**row))
        session.flush()
        for row in kd.USERS:
            session.merge(User(**row))
        session.flush()
        for row in kd.SETTLEMENTS:
            session.merge(Settlement(**{**row, "settlement_date": _d(row["settlement_date"])}))
        session.flush()
        for row in kd.TRANSACTIONS:
            payload = dict(row)
            payload["settlement_date"] = _d(payload["settlement_date"])
            payload["chargeback_date"] = _d(payload["chargeback_date"])
            session.merge(Transaction(**payload))
        session.flush()
        for row in kd.CHARGEBACKS:
            session.merge(Chargeback(**{**row, "chargeback_date": _d(row["chargeback_date"])}))
    engine.dispose()


def _d(value: str | None) -> object:
    import datetime as dt

    return dt.date.fromisoformat(value) if value else None


@pytest.fixture
def app_settings(db_env: DbEnv, settings):  # type: ignore[no-untyped-def]
    """Unit-test settings with the real application/analytics role URLs."""
    os.environ["DATABASE_URL"] = db_env.app_url
    os.environ["ANALYTICS_DATABASE_URL"] = db_env.analytics_url
    from app.config import get_settings
    from app.db.session import analytics_engine, app_engine

    get_settings.cache_clear()
    app_engine.cache_clear()
    analytics_engine.cache_clear()
    return settings.model_copy(
        update={
            "database_url": _secret(db_env.app_url),
            "analytics_database_url": _secret(db_env.analytics_url),
        }
    )


def _secret(value: str):  # type: ignore[no-untyped-def]
    from pydantic import SecretStr

    return SecretStr(value)


@pytest.fixture
def ro_session(app_settings) -> Iterator[Session]:  # type: ignore[no-untyped-def]
    """Analytics session: analytics_ro role, read-only transaction defaults."""
    from app.db.session import analytics_engine

    with Session(analytics_engine()) as session:
        yield session


@pytest.fixture
def app_db_session(app_settings) -> Iterator[Session]:  # type: ignore[no-untyped-def]
    """Application session: merchant_app role (tenant reads, audit inserts only)."""
    from app.db.session import app_engine

    with Session(app_engine()) as session:
        yield session


@pytest.fixture
def admin_session(db_env: DbEnv) -> Iterator[Session]:
    """Privileged session for asserting database state. Tests use it only to inspect or to attempt
    constraint violations, and they roll back."""
    engine = create_engine(make_url(db_env.admin_url).set(drivername="postgresql+psycopg"))
    with Session(engine) as session:
        yield session
    engine.dispose()
