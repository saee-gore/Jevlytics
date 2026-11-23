"""Structured audit events. Store codes, hashes and latencies only.

Never stored: raw questions (only a SHA-256), LLM prompts or outputs, result rows, tokens, or keys.
"""

from __future__ import annotations

import hashlib
import json
import logging
import uuid

from sqlalchemy import text
from sqlalchemy.orm import Session

logger = logging.getLogger("audit")

_ALLOWED_DETAIL_KEYS = frozenset({"reason", "row_count", "date_span_days", "clarification_code"})
_INSERT_AUDIT = """
INSERT INTO audit_events (
    request_id, merchant_id, user_id, event_type, jev_scope, jev_tool, jev_latency_ms,
    policy_outcome, tool_used, response_status, question_sha256, detail
) VALUES (
    CAST(:request_id AS uuid), :merchant_id, :user_id, :event_type, :jev_scope, :jev_tool,
    :jev_latency_ms, :policy_outcome, :tool_used, :response_status, :question_sha256,
    CAST(:detail AS jsonb)
)
"""


def question_digest(question: str) -> str:
    return hashlib.sha256(question.encode("utf-8")).hexdigest()


def record_event(
    session: Session,
    *,
    request_id: uuid.UUID,
    event_type: str,
    response_status: str,
    question: str,
    merchant_id: str | None = None,
    user_id: str | None = None,
    jev_scope: str | None = None,
    jev_tool: str | None = None,
    jev_latency_ms: int | None = None,
    policy_outcome: str | None = None,
    tool_used: str | None = None,
    detail: dict[str, str | int] | None = None,
) -> None:
    safe_detail = {k: v for k, v in (detail or {}).items() if k in _ALLOWED_DETAIL_KEYS}
    # Explicit parameterised INSERT with no RETURNING. The application role holds INSERT but not
    # SELECT on audit_events. ORM and Core inserts on PostgreSQL add RETURNING, which needs SELECT,
    # so the statement is written by hand to keep the grant minimal.
    session.execute(
        text(_INSERT_AUDIT),
        {
            "request_id": request_id,
            "merchant_id": merchant_id,
            "user_id": user_id,
            "event_type": event_type,
            "jev_scope": jev_scope,
            "jev_tool": jev_tool,
            "jev_latency_ms": jev_latency_ms,
            "policy_outcome": policy_outcome,
            "tool_used": tool_used,
            "response_status": response_status,
            "question_sha256": question_digest(question),
            "detail": json.dumps(safe_detail, sort_keys=True),
        },
    )
    session.commit()
    logger.info(
        "audit event=%s request_id=%s status=%s policy=%s tool=%s scope=%s",
        event_type,
        request_id,
        response_status,
        policy_outcome,
        tool_used,
        jev_scope,
    )
