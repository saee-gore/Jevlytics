"""Central registry: closed set, role filtering, runtime disable, and no tenant fields in any schema."""

from __future__ import annotations

import pytest
from pydantic import BaseModel

from app.orchestration import schemas as s
from app.orchestration.tool_registry import NO_TOOL, ToolRegistry, ToolSpec, build_registry


def test_registry_contains_every_required_tool() -> None:
    names = {spec.name for spec in build_registry().enabled()}
    assert names == {
        "get_transaction_volume",
        "get_transaction_count",
        "get_decline_reasons",
        "get_decline_rate",
        "get_settlement_volume",
        "get_chargeback_rate",
        "get_card_type_performance",
        "get_transaction_volume_by_region",
        "get_fraud_indicators",
    }


def test_disabled_capabilities_are_removed_without_code_changes() -> None:
    registry = build_registry(frozenset({"get_fraud_indicators"}))
    assert registry.get("get_fraud_indicators") is not None
    assert "get_fraud_indicators" not in {spec.name for spec in registry.enabled()}


def test_viewer_role_excludes_analyst_tools() -> None:
    viewer = {spec.name for spec in build_registry().enabled_for_role("VIEWER")}
    analyst = {spec.name for spec in build_registry().enabled_for_role("ANALYST")}
    assert "get_fraud_indicators" not in viewer
    assert "get_fraud_indicators" in analyst
    assert viewer < analyst


def test_unknown_role_gets_no_tools() -> None:
    assert build_registry().enabled_for_role("ADMIN") == []


def test_no_tool_is_reserved() -> None:
    # NO_TOOL has no analytics implementation, so ToolSpec construction must refuse it. The registry
    # check for the reserved name is a second guard; both must hold.
    with pytest.raises(ValueError, match="no analytics implementation"):
        ToolSpec(NO_TOOL, "x", s.VolumeArgs, "VIEWER")


def test_duplicate_names_are_rejected() -> None:
    spec = build_registry().get("get_transaction_volume")
    assert spec is not None
    with pytest.raises(ValueError):
        ToolRegistry((spec, spec), frozenset())


def test_registry_entry_without_implementation_is_rejected() -> None:
    with pytest.raises(ValueError):
        ToolSpec("not_implemented", "x", s.VolumeArgs, "VIEWER")


@pytest.mark.parametrize("spec", build_registry().enabled(), ids=lambda sp: sp.name)
def test_argument_schemas_carry_no_tenant_or_sql_fields(spec: ToolSpec) -> None:
    properties = set(spec.json_schema.get("properties", {}))  # type: ignore[union-attr]
    forbidden = {"merchant_id", "tenant", "tenant_id", "role", "user_id", "sql", "query"}
    assert properties.isdisjoint(forbidden)
    assert spec.json_schema.get("additionalProperties") is False  # type: ignore[union-attr]


def test_argument_models_forbid_extra_keys() -> None:
    for spec in build_registry().enabled():
        assert issubclass(spec.args_model, BaseModel)
        assert spec.args_model.model_config.get("extra") == "forbid"


def test_chat_request_has_no_tenant_field() -> None:
    assert set(s.ChatRequest.model_fields) == {"message"}
    with pytest.raises(ValueError):
        s.ChatRequest.model_validate({"message": "hi", "merchant_id": "merchant_002"})
