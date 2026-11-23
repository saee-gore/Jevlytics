# API reference

This page describes the backend's HTTP endpoints. The routes are defined in `app/main.py`, `app/api/routes_chat.py` and `app/api/routes_transactions.py`. The interactive OpenAPI page is at `/docs` when the backend is running.

## Conventions

**Base URL.** `http://localhost:8000` in local development.

**Authentication.** Every endpoint except `/health` needs a bearer token:

```
Authorization: Bearer <token>
```

A missing or invalid token returns `401` with the detail `Authentication required.`

**Merchant scope.** The merchant is always taken from the verified token. No request field or query parameter can set it.

**Rate limit.** Authenticated endpoints count requests per user per minute, set by `RATE_LIMIT_PER_MINUTE`. A user who exceeds the limit gets `429` with the detail `Too many requests. Please wait a minute and try again.`

**Errors.** Errors use the standard FastAPI body, `{"detail": "..."}`.

**Request IDs.** Successful responses include a `request_id`, which is useful when reading the audit log.

## Summary of endpoints

| Method | Path | Authentication | Minimum role |
|---|---|---|---|
| GET | `/health` | No | None |
| POST | `/chat` | Yes | Any role that can use at least one enabled tool |
| GET | `/capabilities` | Yes | Any |
| GET | `/transactions` | Yes | ANALYST |
| GET | `/transactions/summary` | Yes | Any |

---

## GET /health

Checks that the service is running and can reach the database. It does not need a token.

**Response `200`**

```json
{
  "status": "ok",
  "database": "ok"
}
```

`status` is `"degraded"` and `database` is `"unavailable"` when the database check fails.

Outside production (`APP_ENV` not set to `production`), the response also contains a `configured` object. It reports whether each dependency is set, as true or false only. It never returns key values:

```json
"configured": { "auth": true, "jev": true, "llm": false }
```

---

## POST /chat

Sends a question to the assistant. The workflow runs the cross-merchant screen, the Jev screen, tool selection, parameter extraction, the policy engine and the analytics layer, in that order. See [overview](../architecture/overview.md#chat-request).

**Request body**

| Field | Type | Rules |
|---|---|---|
| `message` | string | Required. 1 to 4000 characters. Leading and trailing spaces are removed. |

No other fields are accepted. Unknown fields return a validation error.

```json
{
  "message": "What was my decline rate in October 2026?"
}
```

**Response `200`**

| Field | Type | Notes |
|---|---|---|
| `status` | string | One of `answered`, `clarification_required`, `unsupported`, `blocked` or `temporarily_unavailable` |
| `answer` | string or null | The written answer. May be null. |
| `tool_used` | string or null | The tool that ran, if any |
| `filters` | object or null | The parameters the tool used |
| `data` | object or null | Figures returned by the tool. Present only with `answered`. |
| `chart` | object or null | Chart data, if the tool provides it |
| `request_id` | string | Identifier for this request |

A non-`answered` status means no figures were returned. Refusals and failures are normal responses, not HTTP errors. They return `200` with the status set.

**Other responses**

| Status | When |
|---|---|
| `401` | Missing or invalid token |
| `413` | The message is longer than `MAX_MESSAGE_CHARS`. The detail is `Message is too long.` |
| `422` | The body fails validation, for example an empty message |
| `429` | Rate limit exceeded |

---

## GET /capabilities

Lists the analytics tools the signed-in user can use. The list is filtered by the user's role and by `DISABLED_CAPABILITIES`.

**Response `200`**

```json
{
  "role": "ANALYST",
  "capabilities": [
    { "name": "get_decline_rate", "description": "...", "min_role": "VIEWER" }
  ],
  "request_id": "..."
}
```

| Field | Type | Notes |
|---|---|---|
| `role` | string | The caller's role |
| `capabilities` | array | Each item has `name`, `description` and `min_role` |
| `request_id` | string | Identifier for this request |

---

## GET /transactions

Returns a page of transactions for the caller's merchant. Requires the ANALYST role.

**Query parameters**

| Parameter | Required | Type | Rules |
|---|---|---|---|
| `start` | Yes | date (`YYYY-MM-DD`) | First day, inclusive |
| `end` | Yes | date (`YYYY-MM-DD`) | Last day, inclusive. Must not be before `start`. |
| `status` | No | string | `APPROVED`, `DECLINED`, `PENDING`, `REFUNDED` or `REVERSED` |
| `card_type` | No | string | `CREDIT` or `DEBIT` |
| `card_network` | No | string | 1 to 16 characters, uppercase letters and underscores only |
| `limit` | No | integer | 1 to 100. Default 50. |
| `offset` | No | integer | 0 to 100000. Default 0. |

The date range may not exceed 366 days.

**Response `200`**

| Field | Type | Notes |
|---|---|---|
| `filters` | object | The filters applied |
| `total` | integer | Number of matching transactions |
| `limit` | integer | The limit used |
| `offset` | integer | The offset used |
| `transactions` | array | Each item has `transaction_id`, `transaction_timestamp`, `card_type`, `card_network`, `amount`, `currency`, `status`, `decline_reason` (may be null) and `region` |
| `request_id` | string | Identifier for this request |

**Errors**

| Status | When |
|---|---|
| `401` | Missing or invalid token |
| `403` | The caller's role is below ANALYST. The detail is `Your role cannot list transactions.` |
| `404` | The merchant does not exist. The detail is `Merchant not found.` |
| `422` | `end` is before `start`, or the range is longer than 366 days |
| `429` | Rate limit exceeded |

---

## GET /transactions/summary

Returns summary figures for the caller's merchant over a date range. It has no role check beyond authentication.

**Query parameters**

| Parameter | Required | Type | Rules |
|---|---|---|---|
| `start` | Yes | date (`YYYY-MM-DD`) | First day, inclusive |
| `end` | Yes | date (`YYYY-MM-DD`) | Last day, inclusive. Must not be before `start`. |

The date range may not exceed 366 days.

**Response `200`**

| Field | Type | Notes |
|---|---|---|
| `filters` | object | The date range applied |
| `by_status` | array | Each item has `status` and `transaction_count` |
| `by_card_network` | array | Each item has `card_network`, `transaction_count`, `approved_count`, `declined_count` and `decline_rate` (may be null) |
| `approved_volume_by_currency` | array | Each item has `currency`, `approved_count` and `approved_volume` |
| `decline_rate` | number or null | Null when there are no transactions to divide by |
| `request_id` | string | Identifier for this request |

**Errors**

| Status | When |
|---|---|
| `401` | Missing or invalid token |
| `404` | The merchant does not exist. The detail is `Merchant not found.` |
| `422` | `end` is before `start`, or the range is longer than 366 days |
| `429` | Rate limit exceeded |
