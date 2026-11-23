"""Jev adapter: typed parsing, closed-set validation, and fail-closed behaviour. No network."""

from __future__ import annotations

from types import SimpleNamespace
from typing import Any

import pytest

from app.jev.adapter import TypeSafeJevAdapter
from app.jev.decisions import (
    NO_TOOL_KEY,
    JevInvalidOutputError,
    JevUnavailableError,
    ScopeLabel,
)


class FakeSdk:
    """Stands in for typesafe_sdk.TypeSafeClient. Records the questions it was asked."""

    def __init__(self, response: Any = None, error: BaseException | None = None) -> None:
        self.response = response
        self.error = error
        self.calls: list[dict[str, Any]] = []

    def system_one(self, *, state: Any, questions: Any, model: Any = None, **_: Any) -> Any:
        self.calls.append({"state": state, "questions": questions, "model": model})
        if self.error is not None:
            raise self.error
        return self.response


def _screen_response(label: str = "SUPPORTED_ANALYTICS", conf: Any = 0.9, risk: Any = 0.02) -> Any:
    return SimpleNamespace(
        choices={"scope": SimpleNamespace(choice=label, confidence=conf, probabilities={label: conf})},
        nouls={"risk": SimpleNamespace(noul=risk)},
    )


def _tool_response(tool: str = "get_transaction_volume", conf: Any = 0.88) -> Any:
    return SimpleNamespace(choices={"tool": SimpleNamespace(choice=tool, confidence=conf)}, nouls={})


CHOICES = {"get_transaction_volume": "Total volume.", "get_decline_rate": "Decline rate."}


def test_screen_parses_typed_answers_and_sends_the_caller_and_the_message() -> None:
    sdk = FakeSdk(response=_screen_response())
    result = TypeSafeJevAdapter(sdk).screen_request("How many transactions last month?", "merchant_001")  # type: ignore[arg-type]
    assert result.scope.label is ScopeLabel.SUPPORTED_ANALYTICS
    assert result.scope.confidence == 0.9
    assert result.risk.risk_probability == 0.02
    state = sdk.calls[0]["state"]
    assert "Caller's own merchant (set by the server): merchant_001" in state
    assert state.endswith("Untrusted message:\nHow many transactions last month?")


def test_screen_tells_jev_to_refuse_other_merchants_however_they_are_worded() -> None:
    sdk = FakeSdk(response=_screen_response())
    TypeSafeJevAdapter(sdk).screen_request("hi", "merchant_002")  # type: ignore[arg-type]
    instructions = sdk.calls[0]["questions"]["scope"].instructions
    assert "merchant two" in instructions
    assert "the other merchant" in instructions
    assert "PROMPT_INJECTION_OR_POLICY_BYPASS" in instructions
    assert sdk.calls[0]["state"].startswith("Caller's own merchant (set by the server): merchant_002")


def test_screen_criteria_cover_exactly_the_closed_label_set() -> None:
    sdk = FakeSdk(response=_screen_response())
    TypeSafeJevAdapter(sdk).screen_request("hi", "merchant_001")  # type: ignore[arg-type]
    criteria = sdk.calls[0]["questions"]["scope"].criteria
    assert set(criteria) == {label.value for label in ScopeLabel}


def test_label_outside_closed_set_is_rejected() -> None:
    sdk = FakeSdk(response=_screen_response(label="ALLOW_EVERYTHING"))
    with pytest.raises(JevInvalidOutputError):
        TypeSafeJevAdapter(sdk).screen_request("hi", "merchant_001")  # type: ignore[arg-type]


@pytest.mark.parametrize("bad", [1.5, -0.1, float("nan"), "0.9", None, True])
def test_non_probability_confidence_is_rejected(bad: Any) -> None:
    sdk = FakeSdk(response=_screen_response(conf=bad))
    with pytest.raises(JevInvalidOutputError):
        TypeSafeJevAdapter(sdk).screen_request("hi", "merchant_001")  # type: ignore[arg-type]


def test_missing_risk_answer_is_rejected() -> None:
    response = SimpleNamespace(
        choices={"scope": SimpleNamespace(choice="OUT_OF_SCOPE", confidence=0.9)}, nouls={}
    )
    with pytest.raises(JevInvalidOutputError):
        TypeSafeJevAdapter(FakeSdk(response=response)).screen_request("hi", "merchant_001")  # type: ignore[arg-type]


@pytest.mark.parametrize("error", [RuntimeError("connection reset"), TimeoutError("slow")])
def test_sdk_or_transport_failure_fails_closed(error: BaseException) -> None:
    with pytest.raises(JevUnavailableError):
        TypeSafeJevAdapter(FakeSdk(error=error)).screen_request("hi", "merchant_001")  # type: ignore[arg-type]


def test_select_tool_accepts_only_supplied_choices() -> None:
    adapter = TypeSafeJevAdapter(FakeSdk(response=_tool_response()))  # type: ignore[arg-type]
    decision = adapter.select_tool("decline rate?", CHOICES)
    assert decision.tool_name == "get_transaction_volume"
    assert decision.confidence == 0.88


def test_select_tool_rejects_name_not_in_registry_choices() -> None:
    # Prompt-injection style answer: Jev names a tool the server never offered.
    adapter = TypeSafeJevAdapter(FakeSdk(response=_tool_response(tool="export_raw_rows")))  # type: ignore[arg-type]
    with pytest.raises(JevInvalidOutputError):
        adapter.select_tool("export everything", CHOICES)


def test_select_tool_offers_no_tool_option_to_jev() -> None:
    sdk = FakeSdk(response=_tool_response(tool=NO_TOOL_KEY))
    decision = TypeSafeJevAdapter(sdk).select_tool("weather?", CHOICES)  # type: ignore[arg-type]
    assert decision.tool_name == NO_TOOL_KEY
    criteria = sdk.calls[0]["questions"]["tool"].criteria
    assert set(criteria) == set(CHOICES) | {NO_TOOL_KEY}


def test_select_tool_with_no_choices_is_refused_without_calling_jev() -> None:
    sdk = FakeSdk(response=_tool_response())
    with pytest.raises(JevInvalidOutputError):
        TypeSafeJevAdapter(sdk).select_tool("x", {})  # type: ignore[arg-type]
    assert sdk.calls == []


def test_select_tool_missing_answer_is_rejected() -> None:
    response = SimpleNamespace(choices={}, nouls={})
    with pytest.raises(JevInvalidOutputError):
        TypeSafeJevAdapter(FakeSdk(response=response)).select_tool("x", CHOICES)  # type: ignore[arg-type]


def test_select_tool_sdk_failure_fails_closed() -> None:
    with pytest.raises(JevUnavailableError):
        TypeSafeJevAdapter(FakeSdk(error=ConnectionError("down"))).select_tool("x", CHOICES)  # type: ignore[arg-type]
