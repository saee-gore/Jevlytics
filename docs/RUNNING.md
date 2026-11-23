# Running Jevlytics: reference

This page lists settings, test commands and common problems. For step-by-step setup, see [GETTING_STARTED.md](../GETTING_STARTED.md).

## Backend settings

The backend reads these settings from `.env` in the project folder. `.env.example` lists them with placeholder values.

| Setting | Default | Notes |
|---|---|---|
| `DATABASE_URL` | none | Connection for the API. Use the `merchant_app` role. |
| `ANALYTICS_DATABASE_URL` | none | Read-only connection for analytics queries |
| `MIGRATION_DATABASE_URL` | none | Owner connection used by migrations |
| `JWT_SECRET` | none | At least 32 characters. Without it, sign-in is not configured. |
| `TYPESAFE_API_KEY` | none | Needed for Jev |
| `TYPESAFE_DEFAULT_MODEL` | `jev-latest` | Jev model alias |
| `JEV_SCOPE_MIN_CONFIDENCE` | set in `app/config.py` | See [JEV_AND_LLM.md](docs/JEV_AND_LLM.md) |
| `JEV_TOOL_MIN_CONFIDENCE` | set in `app/config.py` | See [JEV_AND_LLM.md](docs/JEV_AND_LLM.md) |
| `JEV_RISK_BLOCK_THRESHOLD` | set in `app/config.py` | See [JEV_AND_LLM.md](docs/JEV_AND_LLM.md) |
| `ANTHROPIC_API_KEY` | none | Needed for Claude |
| `LLM_MODEL` | `claude-haiku-5-5` | Claude model name |
| `LLM_TIMEOUT_SECONDS` | set in `app/config.py` | Time limit for each call |
| `LLM_MAX_TOKENS` | set in `app/config.py` | Output limit for each call |
| `MAX_MESSAGE_CHARS` | set in `app/config.py` | Largest accepted message |
| `MAX_DATE_SPAN_DAYS` | set in `app/config.py` | Longest accepted date range |
| `RATE_LIMIT_PER_MINUTE` | set in `app/config.py` | Requests allowed per user per minute |
| `DISABLED_CAPABILITIES` | empty | Names of tools to turn off |

## Frontend settings

The frontend reads these from `frontend/.env.local`. `frontend/.env.example` lists them.

| Setting | Values | Notes |
|---|---|---|
| `NEXT_PUBLIC_DATA_MODE` | `mock` (default) or `live` | Read when the app is built. Build again after a change. |
| `BACKEND_URL` | for example `http://127.0.0.1:8000` | Used by the server to reach the API |

## Analytics and Jev without keys

Without `TYPESAFE_API_KEY` or `ANTHROPIC_API_KEY`, questions that need that service return `temporarily_unavailable`.

## Test commands

These commands were run during development. Run them from the project folder with the environment active.

```bash
python -m pytest tests/unit -q
ruff check app tests scripts
mypy app
```

From the `frontend` folder:

```bash
npx tsc --noEmit
npm run build
```

The browser tests in `frontend/e2e/` need Chrome and a running dashboard. For the coverage of each file, see [FRONTEND.md](docs/FRONTEND.md#browser-tests).

## Common problems

| Symptom | Likely cause and fix |
|---|---|
| `GET /` returns 404 | The API has no root route. Use `/health` or `/docs`. |
| Questions return `temporarily_unavailable` | A key is missing. Check `TYPESAFE_API_KEY` and `ANTHROPIC_API_KEY`. |
| `/health` shows the database as unavailable | The passwords in `.env` do not match the passwords used during migration. |
| The dashboard shows an old build | Run `npm run build` again, then restart the server. |
| A port is already in use | Another process holds the port. Stop it, or stop the earlier server. |
