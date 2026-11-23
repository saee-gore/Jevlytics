"""Deterministic policy engine: the final allow/deny decision for any analytics execution.

Jev and the LLM are advisers. This module is the enforcement point. Each check below is explicit:

    allow = authenticated_user
            and merchant_context_is_valid
            and request_is_in_scope                 (Jev scope label, re-checked here)
            and tool_name_is_registered_and_enabled
            and user_role_can_use_tool
            and arguments_match_schema              (strict Pydantic, extra keys forbidden)
            and date_range_is_within_policy

A Jev SUPPORTED label or a tool name alone never grants execution.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from datetime import date, timedelta
from enum import StrEnum
from typing import Protocol, cast

from pydantic import BaseModel, ValidationError

from app.analytics.service import AnalyticsQuery
from app.auth.tenant_context import TenantContext
from app.orchestration.schemas import DateRange
from app.orchestration.tool_registry import NO_TOOL, ROLE_RANK, ToolRegistry, ToolSpec


class PolicyOutcome(StrEnum):
    ALLOW = "ALLOW"
    DENY_CONTEXT = "DENY_CONTEXT"
    DENY_SCOPE = "DENY_SCOPE"
    DENY_NO_TOOL = "DENY_NO_TOOL"
    DENY_UNKNOWN_TOOL = "DENY_UNKNOWN_TOOL"
    DENY_DISABLED = "DENY_DISABLED"
    DENY_ROLE = "DENY_ROLE"
    DENY_SCHEMA = "DENY_SCHEMA"
    DENY_DATE_POLICY = "DENY_DATE_POLICY"
    DENY_RISK = "DENY_RISK"
    DENY_JEV_INVALID = "DENY_JEV_INVALID"


class _HasDateRange(Protocol):
    date_range: DateRange


@dataclass(frozen=True)
class PolicyDecision:
    outcome: PolicyOutcome
    tool: ToolSpec | None = None
    query: AnalyticsQuery | None = None
    message: str | None = None


@dataclass(frozen=True)
class PolicyLimits:
    max_date_span_days: int
    today_local: date


def _date_range_of(parsed: BaseModel) -> DateRange:
    # Every tool args model declares a validated date_range (see schemas.py).
    return cast(_HasDateRange, parsed).date_range


def _query_from(spec: ToolSpec, parsed: BaseModel) -> AnalyticsQuery:
    date_range = _date_range_of(parsed)
    return AnalyticsQuery(
        start=date_range.start,
        end=date_range.end,
        card_type=getattr(parsed, "card_type", None),
        card_network=getattr(parsed, "card_network", None),
        currency=getattr(parsed, "currency", None),
        region=getattr(parsed, "region", None),
        status=getattr(parsed, "status", None),
    )


def evaluate_tool_call(
    *,
    context: TenantContext | None,
    registry: ToolRegistry,
    limits: PolicyLimits,
    scope_is_supported: bool,
    jev_tool_name: str | None,
    raw_arguments: Mapping[str, object] | None,
) -> PolicyDecision:
    # 1. Authenticated tenant context must exist and carry a merchant.
    if context is None or not context.merchant_id or not context.role:
        return PolicyDecision(PolicyOutcome.DENY_CONTEXT)

    # 2. Scope: the request must have been classified SUPPORTED by Jev AND be re-validated here.
    if not scope_is_supported:
        return PolicyDecision(PolicyOutcome.DENY_SCOPE)

    # 3. Tool name: must be a registered, enabled tool. Jev's answer is validated against the registry.
    if jev_tool_name is None or jev_tool_name == NO_TOOL:
        return PolicyDecision(PolicyOutcome.DENY_NO_TOOL)
    spec = registry.get(jev_tool_name)
    if spec is None:
        return PolicyDecision(PolicyOutcome.DENY_UNKNOWN_TOOL)
    if not spec.enabled:
        return PolicyDecision(PolicyOutcome.DENY_DISABLED)

    # 4. Role: the database role (already resolved into the context) must meet the tool's minimum.
    if ROLE_RANK.get(context.role, 0) < ROLE_RANK[spec.min_role]:
        return PolicyDecision(PolicyOutcome.DENY_ROLE)

    # 5. Arguments: strict schema. Any extra key, including merchant_id, tenant or SQL, is rejected.
    if raw_arguments is None:
        return PolicyDecision(PolicyOutcome.DENY_SCHEMA)
    try:
        parsed = spec.args_model.model_validate(dict(raw_arguments))
    except ValidationError:
        return PolicyDecision(PolicyOutcome.DENY_SCHEMA)

    # 6. Date-range policy: ordered (already enforced by the model), bounded span, no future dates.
    date_range = _date_range_of(parsed)
    span_days = (date_range.end - date_range.start).days + 1
    if span_days > limits.max_date_span_days:
        return PolicyDecision(
            PolicyOutcome.DENY_DATE_POLICY,
            message=f"Please choose a period of {limits.max_date_span_days} days or fewer.",
        )
    if date_range.end > limits.today_local:
        return PolicyDecision(
            PolicyOutcome.DENY_DATE_POLICY,
            message="Please choose a period that ends today or earlier.",
        )
    if date_range.start < limits.today_local - timedelta(days=3650):
        return PolicyDecision(
            PolicyOutcome.DENY_DATE_POLICY,
            message="Please choose a more recent period.",
        )

    return PolicyDecision(PolicyOutcome.ALLOW, tool=spec, query=_query_from(spec, parsed))
