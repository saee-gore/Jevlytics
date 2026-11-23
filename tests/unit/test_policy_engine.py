"""Deterministic policy engine: every deny reason, and the one allow path."""

from __future__ import annotations

from datetime import date

import pytest

from app.auth.tenant_context import TenantContext
from app.orchestration.policy_engine import PolicyLimits, PolicyOutcome, evaluate_tool_call
from app.orchestration.tool_registry import build_registry

TODAY = date(2026, 11, 20)
LIMITS = PolicyLimits(max_date_span_days=366, today_local=TODAY)
VALID_ARGS = {"date_range": {"start": "2026-10-01", "end": "2026-10-31"}}


def _ctx(role: str = "ANALYST", merchant: str = "merchant_001") -> TenantContext:
    return TenantContext(user_id="u1", merchant_id=merchant, role=role)


def _decide(**overrides: object):  # type: ignore[no-untyped-def]
    kwargs: dict[str, object] = {
        "context": _ctx(),
        "registry": build_registry(),
        "limits": LIMITS,
        "scope_is_supported": True,
        "jev_tool_name": "get_transaction_volume",
        "raw_arguments": dict(VALID_ARGS),
    }
    kwargs.update(overrides)
    return evaluate_tool_call(**kwargs)  # type: ignore[arg-type]


def test_allow_path_builds_query_from_validated_arguments() -> None:
    decision = _decide(raw_arguments={**VALID_ARGS, "currency": "USD"})
    assert decision.outcome is PolicyOutcome.ALLOW
    assert decision.query is not None
    assert decision.query.start == date(2026, 10, 1)
    assert decision.query.end == date(2026, 10, 31)
    assert decision.query.currency == "USD"


def test_denies_missing_context() -> None:
    assert _decide(context=None).outcome is PolicyOutcome.DENY_CONTEXT


def test_denies_when_scope_not_supported_even_with_valid_tool() -> None:
    assert _decide(scope_is_supported=False).outcome is PolicyOutcome.DENY_SCOPE


def test_denies_no_tool_and_missing_tool() -> None:
    assert _decide(jev_tool_name="NO_TOOL").outcome is PolicyOutcome.DENY_NO_TOOL
    assert _decide(jev_tool_name=None).outcome is PolicyOutcome.DENY_NO_TOOL


def test_denies_unknown_tool_name() -> None:
    assert _decide(jev_tool_name="delete_all_transactions").outcome is PolicyOutcome.DENY_UNKNOWN_TOOL


def test_denies_disabled_tool() -> None:
    registry = build_registry(frozenset({"get_transaction_volume"}))
    assert _decide(registry=registry).outcome is PolicyOutcome.DENY_DISABLED


def test_viewer_cannot_use_analyst_only_tool() -> None:
    decision = _decide(
        context=_ctx(role="VIEWER"),
        jev_tool_name="get_fraud_indicators",
        raw_arguments=dict(VALID_ARGS),
    )
    assert decision.outcome is PolicyOutcome.DENY_ROLE


def test_viewer_can_use_viewer_tool() -> None:
    assert _decide(context=_ctx(role="VIEWER")).outcome is PolicyOutcome.ALLOW


@pytest.mark.parametrize(
    "bad_arguments",
    [
        {**VALID_ARGS, "merchant_id": "merchant_002"},  # tenant injection by LLM or prompt
        {**VALID_ARGS, "tenant": "merchant_002"},
        {**VALID_ARGS, "sql": "SELECT 1"},
        {**VALID_ARGS, "card_type": "PREPAID"},  # outside enumeration
        {**VALID_ARGS, "currency": "usd"},  # pattern violation
        {"date_range": {"start": "2026-10-31", "end": "2026-10-01"}},  # inverted
        {},  # missing required date_range
    ],
)
def test_denies_malformed_or_injected_arguments(bad_arguments: dict[str, object]) -> None:
    assert _decide(raw_arguments=bad_arguments).outcome is PolicyOutcome.DENY_SCHEMA


def test_denies_missing_arguments_entirely() -> None:
    assert _decide(raw_arguments=None).outcome is PolicyOutcome.DENY_SCHEMA


def test_denies_span_longer_than_policy() -> None:
    too_long = {"date_range": {"start": "2025-01-01", "end": "2026-10-31"}}
    decision = _decide(raw_arguments=too_long)
    assert decision.outcome is PolicyOutcome.DENY_DATE_POLICY
    assert decision.message is not None


def test_denies_future_end_date() -> None:
    future = {"date_range": {"start": "2026-11-01", "end": "2026-12-31"}}
    assert _decide(raw_arguments=future).outcome is PolicyOutcome.DENY_DATE_POLICY


def test_end_equal_to_today_is_allowed() -> None:
    today_range = {"date_range": {"start": "2026-11-01", "end": "2026-11-20"}}
    assert _decide(raw_arguments=today_range).outcome is PolicyOutcome.ALLOW


def test_jev_allow_alone_is_not_enough_without_valid_arguments() -> None:
    # Jev says SUPPORTED and picks a registered tool with high confidence, but the arguments are
    # empty. Execution must still be denied.
    decision = _decide(scope_is_supported=True, raw_arguments={})
    assert decision.outcome is PolicyOutcome.DENY_SCHEMA
