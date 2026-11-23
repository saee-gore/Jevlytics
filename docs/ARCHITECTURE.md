# Architecture

Jevlytics has three layers. Only the analytics layer calculates figures. Only the orchestration layer decides whether a tool runs.

1. **Analytics.** Runs parameterised SQL against PostgreSQL. The analytics connection is read-only, and each session has a five-second statement timeout.
2. **Orchestration.** A FastAPI service. It checks the signed-in user, derives the merchant from the database record for that user, and applies the tool registry and the policy engine.
3. **Interpretation.** Jev classifies each question and chooses a tool. Claude extracts the tool's parameters and writes the answer. Neither model can run a tool or set the merchant.

## Components

| Path | Responsibility |
|---|---|
| `app/analytics/` | Tool queries and metric definitions |
| `app/auth/` | Token verification and the tenant context |
| `app/api/` | HTTP routes: chat, transactions and capabilities |
| `app/db/` | Database engines and models. Sessions use a five-second statement timeout. |
| `app/jev/` | The Jev adapter and its typed decisions |
| `app/llm/` | The Claude provider, prompts and response builder |
| `app/orchestration/` | Request schemas, the tool registry, the cross-merchant screen, the policy engine, the workflow and the audit log |
| `alembic/` | Database migrations |
| `scripts/` | Data generation and seeding, Jev evaluation, token issuing, and the database role script |
| `data/` | Synthetic CSV files, their manifest and the Jev evaluation cases |
| `tests/` | Unit tests and fakes for Jev and Claude. Also a repository hygiene test. |
| `frontend/` | The Next.js dashboard |

## Chat request

`POST /chat` runs these steps in order, as defined in `app/orchestration/workflow.py`:

1. **Cross-merchant screen.** A deterministic check that refuses messages naming another merchant. It runs before any model.
2. **Jev configuration check.** If Jev is not configured, the request stops.
3. **Jev scope and risk screen.** Jev receives the caller's merchant, set by the server, and the message.
4. **Jev tool choice.** Jev chooses a tool from the tools the caller's role allows, or none.
5. **Claude argument extraction.** Claude returns the tool's parameters, which are checked against a schema.
6. **Policy engine.** Checks the role, that the tool is enabled, the schema, the date span and the merchant scope.
7. **Audit.** The `policy_allow` entry is written before the analytics query runs. If the entry cannot be written, the request stops.
8. **Analytics.** The tool runs with the merchant from the tenant context.
9. **Claude explanation.** Claude writes the answer from the approved result.

A request that fails at any step returns a status instead of figures. The five statuses are `answered`, `clarification_required`, `unsupported`, `blocked` and `temporarily_unavailable`.

## Tools

There are nine analytics tools in `app/orchestration/tool_registry.py`.

| Tool | Minimum role |
|---|---|
| `get_transaction_volume` | VIEWER |
| `get_transaction_count` | VIEWER |
| `get_decline_reasons` | VIEWER |
| `get_decline_rate` | VIEWER |
| `get_settlement_volume` | VIEWER |
| `get_chargeback_rate` | VIEWER |
| `get_card_type_performance` | VIEWER |
| `get_transaction_volume_by_region` | VIEWER |
| `get_fraud_indicators` | ANALYST |

The `DISABLED_CAPABILITIES` setting turns tools off by name. Jev is offered only the enabled tools the caller's role allows, and the policy engine checks Jev's choice again.

The dashboard offers the ANALYST role only. The backend also accepts VIEWER.

## Database roles

The database setup creates three roles:

| Role | Used by |
|---|---|
| `merchant_owner` | Migrations and seeding |
| `merchant_app` | The API |
| `analytics_ro` | The analytics queries, through a read-only session |

## Endpoints

| Method and path | Purpose |
|---|---|
| `GET /health` | Returns the status of the service and the database |
| `POST /chat` | The chat workflow above |
| `GET /capabilities` | The tools available to the caller |
| `GET /transactions` | Transactions for the caller's merchant |
| `GET /transactions/summary` | Summary figures for the caller's merchant |

The merchant is never read from the request body or from the message.
