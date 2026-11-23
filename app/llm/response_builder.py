"""Builds the public ChatResponse. The only place that decides which fields may leave the server.

Invariant: data and filters are populated ONLY for status "answered". Every other status carries
no analytics data, so a blocked or unsupported request cannot leak results.
"""

from __future__ import annotations

from typing import Any

from app.orchestration.schemas import ChatResponse

UNSUPPORTED_MESSAGE = (
    "This assistant answers read-only aggregate analytics about your merchant's card transactions. "
    "It cannot make payments, refunds or changes, and it cannot access other merchants' data."
)
CLARIFY_MESSAGE = (
    "Could you clarify your question? Please name the metric you want and the time period, for "
    "example: 'What was our decline rate for debit cards in October?'"
)
BLOCKED_MESSAGE = "This request can't be processed."
UNAVAILABLE_MESSAGE = "The analytics assistant is temporarily unavailable. Please try again later."
SCOPE_HELP = (
    "Available analytics: transaction volume and counts, decline reasons and rates, settlement "
    "volume, chargeback rate, credit versus debit performance, regional volume, and risk indicators."
)


def answered(
    request_id: str,
    *,
    answer: str,
    tool_used: str,
    filters: dict[str, Any],
    data: dict[str, Any],
) -> ChatResponse:
    return ChatResponse(
        status="answered",
        answer=answer,
        tool_used=tool_used,
        filters=filters,
        data=data,
        chart=None,
        request_id=request_id,
    )


def clarification(request_id: str, text: str | None = None) -> ChatResponse:
    return ChatResponse(
        status="clarification_required",
        answer=text or CLARIFY_MESSAGE,
        request_id=request_id,
    )


def unsupported(request_id: str, text: str | None = None) -> ChatResponse:
    return ChatResponse(
        status="unsupported",
        answer=text or f"{UNSUPPORTED_MESSAGE} {SCOPE_HELP}",
        request_id=request_id,
    )


def blocked(request_id: str) -> ChatResponse:
    return ChatResponse(status="blocked", answer=BLOCKED_MESSAGE, request_id=request_id)


def unavailable(request_id: str) -> ChatResponse:
    return ChatResponse(
        status="temporarily_unavailable",
        answer=UNAVAILABLE_MESSAGE,
        request_id=request_id,
    )
