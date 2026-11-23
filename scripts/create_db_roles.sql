-- Database roles for the merchant analytics demo.
-- Run AFTER migrations (grants reference existing tables). Re-runnable.
--
-- Usage (as a superuser or the owner role):
--   psql "$ADMIN_DATABASE_URL" -v ON_ERROR_STOP=1 \
--        -v app_password="$APP_DB_PASSWORD" \
--        -v ro_password="$ANALYTICS_RO_PASSWORD" \
--        -v owner_password="$OWNER_DB_PASSWORD" \
--        -f scripts/create_db_roles.sql
--
-- Role summary:
--   merchant_owner : owns schema; runs Alembic migrations and seeding. Never used by the API.
--   merchant_app   : API process. Reads tenant tables and users, appends audit_events only.
--   analytics_ro   : analytics layer. SELECT on aggregate-source tables only. No users, no audit.

-- Create roles if missing. psql variables do not interpolate inside $$ blocks, so use \gexec.
SELECT format('CREATE ROLE merchant_owner LOGIN PASSWORD %L', :'owner_password')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'merchant_owner') \gexec

SELECT format('CREATE ROLE merchant_app LOGIN PASSWORD %L', :'app_password')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'merchant_app') \gexec

SELECT format('CREATE ROLE analytics_ro LOGIN PASSWORD %L', :'ro_password')
WHERE NOT EXISTS (SELECT FROM pg_roles WHERE rolname = 'analytics_ro') \gexec

-- Ensure least privilege even if defaults changed.
REVOKE ALL ON SCHEMA public FROM PUBLIC;
GRANT USAGE ON SCHEMA public TO merchant_owner, merchant_app, analytics_ro;
GRANT ALL ON SCHEMA public TO merchant_owner;

-- Owner role: migrations and seeding need full table/sequence rights on the existing schema.
GRANT ALL ON ALL TABLES IN SCHEMA public TO merchant_owner;
GRANT ALL ON ALL SEQUENCES IN SCHEMA public TO merchant_owner;

-- Application role
GRANT SELECT ON merchants, users, transactions, settlements, chargebacks TO merchant_app;
GRANT INSERT ON audit_events TO merchant_app;
GRANT USAGE, SELECT ON SEQUENCE audit_events_id_seq TO merchant_app;

-- Analytics read-only role (no users, no audit_events)
GRANT SELECT ON merchants, transactions, settlements, chargebacks TO analytics_ro;

-- Ensure tables created later by the owner keep these grants for the demo workflow.
ALTER DEFAULT PRIVILEGES FOR ROLE merchant_owner IN SCHEMA public
  GRANT SELECT ON TABLES TO analytics_ro;
