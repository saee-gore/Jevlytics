"""Alembic environment. Uses the privileged MIGRATION_DATABASE_URL only."""

from __future__ import annotations

import os

from sqlalchemy import engine_from_config, pool

from alembic import context
from app.db.models import Base

config = context.config
target_metadata = Base.metadata


def _migration_url() -> str:
    url = os.environ.get("MIGRATION_DATABASE_URL", "").strip()
    if not url:
        raise RuntimeError("MIGRATION_DATABASE_URL must be set for migrations (privileged role).")
    return url


def run_migrations_offline() -> None:
    context.configure(
        url=_migration_url(),
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    section = config.get_section(config.config_ini_section, {})
    section["sqlalchemy.url"] = _migration_url()
    connectable = engine_from_config(section, prefix="sqlalchemy.", poolclass=pool.NullPool)
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata, compare_type=True)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
