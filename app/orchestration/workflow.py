"""Request workflow: Jev screening -> Jev tool choice -> LLM argument extraction -> policy -> analytics
-> LLM explanation. Every failure path fails closed and returns a generic response.

Trust boundaries:
  * merchant_id and role come from TenantContext (database-derived), never from the message.
  * Jev and the LLM return suggestions. Only evaluate_tool_call() can authorise execution.
  * Analytics runs on the read-only session and receives only validated, typed filters.
  * Only the approved aggregate result is passed to the LLM for explanation.
"""

from __future__ import annotations

import logging
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from sqlalchemy.orm import Session

from app.analytics import queries as analytics_queries
from app.analytics.service import MerchantNotFoundError, run_analytics
from app.auth.tenant_context import TenantContext
from app.config import Settings
from app.jev.adapter import JevClassifier
from app.jev.decisions import (
    NO_TOOL_KEY,
    JevInvalidOutputError,
    JevUnavailableError,
    ScopeLabel,
    ScreeningResult,
)
from app.llm import response_builder as rb
from app.llm.provider import LLMOutputError, LLMProvider, LLMUnavailableError
from app.orchestration import audit
from app.orchestration.merchant_refs import foreign_merchant_refs
from app.orchestration.policy_engine import PolicyLimits, PolicyOutcome, evaluate_tool_call
from app.orchestration.schemas import ChatResponse
from app.orchestration.tool_registry import ROLE_RANK, ToolRegistry

logger = logging.getLogger("workflow")

_FAIL_CLOSED = (JevUnavailableError, JevInvalidOutputError)
_LLM_FAIL = (LLMUnavailableError, LLMOutputError)
_UNSUPPORTED_POLICY = {
    PolicyOutcome.DENY_ROLE,
    PolicyOutcome.DENY_DISABLED,
    PolicyOutcome.DENY_UNKNOWN_TOOL,
}
_CLARIFY_POLICY = {PolicyOutcome.DENY_DATE_POLICY, PolicyOutcome.DENY_SCHEMA}


@dataclass(frozen=True)
class WorkflowDeps:
    settings: Settings
    registry: ToolRegistry
    jev: JevClassifier | None
    llm: LLMProvider | None
    now_utc: Callable[[], datetime] = lambda: datetime.now(UTC)


class ChatWorkflow:
    def __init__(self, deps: WorkflowDeps) -> None:
        self._deps = deps

    def handle(
        self,
        *,
        context: TenantContext,
        message: str,
        request_id: uuid.UUID,
        app_session: Session,
        analytics_session: Session,
    ) -> ChatResponse:
        rid = str(request_id)
        try:
            return self._run(context, message, request_id, app_session, analytics_session)
        except Exception:  # last-resort guard: never leak internals, never execute on error
            logger.exception("unhandled workflow failure request_id=%s", rid)
            _safe_rollback(app_session)
            return rb.unavailable(rid)

    # ------------------------------------------------------------------------------------------

    def _run(
        self,
        context: TenantContext,
        message: str,
        request_id: uuid.UUID,
        app_session: Session,
        analytics_session: Session,
    ) -> ChatResponse:
        rid = str(request_id)
        settings = self._deps.settings

        tz_name = _merchant_timezone(app_session, context.merchant_id)
        if tz_name is None:
            return rb.unavailable(rid)
        today_local = self._deps.now_utc().astimezone(ZoneInfo(tz_name)).date()

        def finish(response: ChatResponse, **audit_fields: object) -> ChatResponse:
            _audit_terminal(
                app_session,
                request_id=request_id,
                context=context,
                question=message,
                response=response,
                **audit_fields,  # type: ignore[arg-type]
            )
            return response

        # 0a. Deterministic screen: a message naming another merchant is refused before any model
        # sees it. Independent of Jev, so a misclassification cannot let it through.
        if foreign_merchant_refs(message, context.merchant_id):
            return finish(
                rb.blocked(rid),
                event_type="cross_merchant_reference",
                policy_outcome=PolicyOutcome.DENY_SCOPE.value,
            )

        # 0. Jev must be configured. Without it we cannot classify, so nothing runs.
        jev = self._deps.jev
        if jev is None:
            return finish(rb.unavailable(rid), event_type="jev_not_configured")

        # 1. Scope and risk screening (one Jev request, user text only).
        try:
            screen: ScreeningResult = jev.screen_request(message, context.merchant_id)
        except _FAIL_CLOSED:
            return finish(rb.unavailable(rid), event_type="jev_screen_failed")
        label = screen.scope.label
        scope_value = label.value
        screen_fields: dict[str, object] = {
            "jev_scope": scope_value,
            "jev_latency_ms": screen.latency_ms,
        }

        if screen.risk.risk_probability >= settings.jev_risk_block_threshold:
            return finish(
                rb.blocked(rid),
                event_type="risk_block",
                policy_outcome=PolicyOutcome.DENY_RISK.value,
                **screen_fields,
            )
        if label is ScopeLabel.NEEDS_CLARIFICATION:
            return finish(rb.clarification(rid), event_type="scope", **screen_fields)
        if label is ScopeLabel.OUT_OF_SCOPE:
            return finish(rb.unsupported(rid), event_type="scope", **screen_fields)
        if label in (
            ScopeLabel.SENSITIVE_OR_UNSAFE,
            ScopeLabel.PROMPT_INJECTION_OR_POLICY_BYPASS,
        ):
            return finish(
                rb.blocked(rid),
                event_type="scope",
                policy_outcome=PolicyOutcome.DENY_SCOPE.value,
                **screen_fields,
            )
        if screen.scope.confidence < settings.jev_scope_min_confidence:
            return finish(rb.clarification(rid), event_type="low_confidence_scope", **screen_fields)

        # 2. Tool choice: Jev may choose only among enabled, role-allowed names plus NO_TOOL.
        specs = self._deps.registry.enabled_for_role(context.role)
        if not specs:
            return finish(rb.unsupported(rid), event_type="no_capabilities", **screen_fields)
        choices = {spec.name: spec.description for spec in specs}
        try:
            tool_decision = jev.select_tool(message, choices)
        except _FAIL_CLOSED:
            return finish(rb.unavailable(rid), event_type="jev_tool_failed", **screen_fields)
        tool_fields: dict[str, object] = {
            **screen_fields,
            "jev_tool": tool_decision.tool_name,
            "jev_latency_ms": screen.latency_ms + tool_decision.latency_ms,
        }
        if tool_decision.tool_name == NO_TOOL_KEY:
            return finish(rb.clarification(rid), event_type="no_tool", **tool_fields)
        if tool_decision.confidence < settings.jev_tool_min_confidence:
            return finish(rb.clarification(rid), event_type="low_confidence_tool", **tool_fields)
        spec = self._deps.registry.get(tool_decision.tool_name)
        if spec is None:  # Jev answer not in the registry; policy would also deny
            return finish(rb.clarification(rid), event_type="unknown_tool", **tool_fields)
        # Cheap pre-check so the LLM never sees a question destined for a tool this user cannot run.
        # evaluate_tool_call() below repeats the check and remains the authority.
        if not spec.enabled or ROLE_RANK.get(context.role, 0) < ROLE_RANK[spec.min_role]:
            outcome = PolicyOutcome.DENY_ROLE if spec.enabled else PolicyOutcome.DENY_DISABLED
            return finish(
                rb.unsupported(rid),
                event_type="policy_deny",
                **{**tool_fields, "policy_outcome": outcome.value},
            )

        # 3. LLM extracts arguments for the chosen tool. The LLM cannot choose the tool or merchant.
        llm = self._deps.llm
        if llm is None:
            return finish(rb.unavailable(rid), event_type="llm_not_configured", **tool_fields)
        try:
            raw_arguments = llm.extract_arguments(
                question=message,
                tool_name=spec.name,
                json_schema=spec.json_schema,
                today_local=today_local,
                timezone=tz_name,
            )
        except _LLM_FAIL:
            return finish(rb.unavailable(rid), event_type="llm_extract_failed", **tool_fields)

        # 4. Deterministic policy: the only authority that can allow execution.
        decision = evaluate_tool_call(
            context=context,
            registry=self._deps.registry,
            limits=PolicyLimits(
                max_date_span_days=settings.max_date_span_days,
                today_local=today_local,
            ),
            scope_is_supported=label is ScopeLabel.SUPPORTED_ANALYTICS,
            jev_tool_name=tool_decision.tool_name,
            raw_arguments=raw_arguments,
        )
        policy_fields: dict[str, object] = {**tool_fields, "policy_outcome": decision.outcome.value}
        if decision.outcome is not PolicyOutcome.ALLOW:
            if decision.outcome in _CLARIFY_POLICY:
                response = rb.clarification(rid, decision.message)
            elif decision.outcome in _UNSUPPORTED_POLICY:
                response = rb.unsupported(rid)
            else:
                response = rb.blocked(rid)
            return finish(response, event_type="policy_deny", **policy_fields)

        assert decision.tool is not None and decision.query is not None
        merchant_id = context.merchant_id

        # 5. Strict audit of the execution decision BEFORE any analytics runs. If it cannot be
        #    recorded, we do not execute.
        try:
            audit.record_event(
                app_session,
                request_id=request_id,
                event_type="policy_allow",
                response_status="pending",
                question=message,
                merchant_id=merchant_id,
                user_id=context.user_id,
                jev_scope=scope_value,
                jev_tool=spec.name,
                jev_latency_ms=int(policy_fields["jev_latency_ms"] or 0),  # type: ignore[call-overload]
                policy_outcome=PolicyOutcome.ALLOW.value,
                tool_used=spec.name,
            )
        except SQLAlchemyError:
            _safe_rollback(app_session)
            logger.exception("could not record execution decision request_id=%s", rid)
            return rb.unavailable(rid)

        # 6. Analytics on the read-only session, scoped by the trusted merchant_id.
        try:
            result = run_analytics(analytics_session, spec.name, merchant_id, decision.query)
        except (SQLAlchemyError, MerchantNotFoundError):
            _safe_rollback(analytics_session)
            logger.exception("analytics execution failed request_id=%s tool=%s", rid, spec.name)
            return finish(rb.unavailable(rid), event_type="analytics_failed", **policy_fields)

        filters = result.pop("filters")
        # 7. LLM explains ONLY the approved aggregate. Nothing else is sent.
        try:
            answer = llm.explain(
                question=message,
                tool_name=spec.name,
                approved_payload={"filters": filters, "result": result},
            )
        except _LLM_FAIL:
            return finish(rb.unavailable(rid), event_type="llm_explain_failed", **policy_fields)

        response = rb.answered(
            rid,
            answer=answer,
            tool_used=spec.name,
            filters=filters,
            data=result,
        )
        return finish(response, event_type="answered", **policy_fields)


# --- helpers ----------------------------------------------------------------------------------------


def _merchant_timezone(session: Session, merchant_id: str) -> str | None:
    row = session.execute(text(analytics_queries.MERCHANT_TIMEZONE), {"merchant_id": merchant_id}).first()
    return str(row.timezone) if row is not None else None


def _safe_rollback(session: Session) -> None:
    try:
        session.rollback()
    except SQLAlchemyError:
        logger.exception("rollback failed")


def _audit_terminal(
    session: Session,
    *,
    request_id: uuid.UUID,
    context: TenantContext,
    question: str,
    response: ChatResponse,
    event_type: str,
    jev_scope: object = None,
    jev_tool: object = None,
    jev_latency_ms: object = None,
    policy_outcome: object = None,
) -> None:
    """Best-effort terminal audit. A failure here is logged; the response is still safe."""
    try:
        audit.record_event(
            session,
            request_id=request_id,
            event_type=event_type,
            response_status=response.status,
            question=question,
            merchant_id=context.merchant_id,
            user_id=context.user_id,
            jev_scope=str(jev_scope) if jev_scope is not None else None,
            jev_tool=str(jev_tool) if jev_tool is not None else None,
            jev_latency_ms=int(jev_latency_ms) if isinstance(jev_latency_ms, int) else None,
            policy_outcome=str(policy_outcome) if policy_outcome is not None else None,
            tool_used=response.tool_used,
        )
    except SQLAlchemyError:
        _safe_rollback(session)
        logger.exception("terminal audit write failed request_id=%s", request_id)
