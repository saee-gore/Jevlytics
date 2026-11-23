#!/usr/bin/env bash
# One-shot local bootstrap: schema, roles, synthetic demo data.
# Runs as the PostgreSQL superuser for the first two steps, because the role script grants on
# tables that the migration creates. Seeding runs as the owner role, as the design requires.
set -euo pipefail

: "${ADMIN_DATABASE_URL:?ADMIN_DATABASE_URL is required}"
: "${OWNER_DATABASE_URL:?OWNER_DATABASE_URL is required}"
: "${APP_DB_PASSWORD:?APP_DB_PASSWORD is required}"
: "${ANALYTICS_RO_PASSWORD:?ANALYTICS_RO_PASSWORD is required}"
: "${OWNER_DB_PASSWORD:?OWNER_DB_PASSWORD is required}"

cd "$(dirname "$0")/.."

echo "[migrate] alembic upgrade head"
# Alembic must use the psycopg 3 driver; psql takes the plain postgresql:// form.
ALEMBIC_ADMIN_URL="$(printf '%s' "$ADMIN_DATABASE_URL" | sed 's#^postgresql://#postgresql+psycopg://#')"
MIGRATION_DATABASE_URL="$ALEMBIC_ADMIN_URL" alembic upgrade head

echo "[migrate] database roles"
psql "$ADMIN_DATABASE_URL" -v ON_ERROR_STOP=1 \
  -v app_password="$APP_DB_PASSWORD" \
  -v ro_password="$ANALYTICS_RO_PASSWORD" \
  -v owner_password="$OWNER_DB_PASSWORD" \
  -f scripts/create_db_roles.sql

echo "[migrate] seed synthetic demo data (owner role)"
MIGRATION_DATABASE_URL="$OWNER_DATABASE_URL" python scripts/seed_database.py

echo "[migrate] done"
