"""Test doubles for Jev and the LLM. They record every call so tests can assert what was (not) sent."""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from datetime import date
from typing import Any

from app.jev.decisions import (
    RiskDecision,
    ScopeDecision,
    ScopeLabel,
    ScreeningResult,
    ToolDecision,
)


@dataclass
class FakeJev:
    label: ScopeLabel = ScopeLabel.SUPPORTED_ANALYTICS
    scope_confidence: float = 0.95
    risk_probability: float = 0.01
    tool_name: str = "get_transaction_volume"
    tool_confidence: float = 0.92
    screen_error: Exception | None = None
    tool_error: Exception | None = None
    screen_calls: list[str] = field(default_factory=list)
    tool_calls: list[tuple[str, dict[str, str]]] = field(default_factory=list)

    def screen_request(self, message: str, caller_merchant_id: str) -> ScreeningResult:
        self.screen_calls.append(message)
        if self.screen_error is not None:
            raise self.screen_error
        return ScreeningResult(
            scope=ScopeDecision(label=self.label, confidence=self.scope_confidence),
            risk=RiskDecision(risk_probability=self.risk_probability),
            latency_ms=7,
        )

    def select_tool(self, message: str, choices: Mapping[str, str]) -> ToolDecision:
        self.tool_calls.append((message, dict(choices)))
        if self.tool_error is not None:
            raise self.tool_error
        return ToolDecision(tool_name=self.tool_name, confidence=self.tool_confidence, latency_ms=9)


@dataclass
class FakeLLM:
    arguments: dict[str, Any] = field(
        default_factory=lambda: {"date_range": {"start": "2026-03-01", "end": "2026-03-04"}}
    )
    explanation: str = "Fake explanation of the approved aggregate."
    extract_error: Exception | None = None
    explain_error: Exception | None = None
    extract_calls: list[dict[str, Any]] = field(default_factory=list)
    explain_calls: list[dict[str, Any]] = field(default_factory=list)

    def extract_arguments(
        self,
        *,
        question: str,
        tool_name: str,
        json_schema: dict[str, Any],
        today_local: date,
        timezone: str,
    ) -> dict[str, Any]:
        self.extract_calls.append(
            {
                "question": question,
                "tool_name": tool_name,
                "json_schema": json_schema,
                "today_local": today_local,
                "timezone": timezone,
            }
        )
        if self.extract_error is not None:
            raise self.extract_error
        return dict(self.arguments)

    def explain(self, *, question: str, tool_name: str, approved_payload: dict[str, Any]) -> str:
        self.explain_calls.append(
            {"question": question, "tool_name": tool_name, "approved_payload": approved_payload}
        )
        if self.explain_error is not None:
            raise self.explain_error
        return self.explanation
