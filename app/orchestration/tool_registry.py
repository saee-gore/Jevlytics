"""Central capability registry: the ONLY list of analytics tools the system can run.

To enable or disable a capability without rewriting prompts, change `enabled` here or list the name
in the DISABLED_CAPABILITIES environment variable. Jev is shown only the enabled, role-allowed names
generated from this registry; it cannot add names. The policy engine re-checks everything.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass, field
from typing import Final

from pydantic import BaseModel

from app.analytics.service import ANALYTICS_FUNCTIONS
from app.orchestration import schemas as s

ROLE_RANK: Final[Mapping[str, int]] = {"VIEWER": 1, "ANALYST": 2}
NO_TOOL: Final = "NO_TOOL"


@dataclass(frozen=True)
class ToolSpec:
    name: str
    description: str
    args_model: type[BaseModel]
    min_role: str
    enabled: bool = True
    # JSON-schema-like hint for the LLM extractor. Derived from the Pydantic model, never hand-typed.
    json_schema: dict[str, object] = field(default_factory=dict)

    def __post_init__(self) -> None:
        if self.name not in ANALYTICS_FUNCTIONS:
            raise ValueError(f"registry entry {self.name!r} has no analytics implementation")
        if self.min_role not in ROLE_RANK:
            raise ValueError(f"unknown role {self.min_role!r}")


CAPABILITIES: tuple[ToolSpec, ...] = (
    ToolSpec(
        "get_transaction_volume",
        "Total approved transaction volume and count per currency, optionally filtered by card type, "
        "card network or currency.",
        s.VolumeArgs,
        "VIEWER",
    ),
    ToolSpec(
        "get_transaction_count",
        "Transaction counts by status for a period, optionally filtered by card type, card network "
        "or status.",
        s.CountArgs,
        "VIEWER",
    ),
    ToolSpec(
        "get_decline_reasons",
        "Most common decline reasons and their counts for a period, optionally filtered by card type "
        "or card network.",
        s.DeclineReasonsArgs,
        "VIEWER",
    ),
    ToolSpec(
        "get_decline_rate",
        "Decline rate for a period, optionally filtered by card type or card network. Includes a "
        "breakdown by card network when no network filter is given.",
        s.DeclineRateArgs,
        "VIEWER",
    ),
    ToolSpec(
        "get_settlement_volume",
        "Settled volume and settlement counts per currency for a period.",
        s.SettlementVolumeArgs,
        "VIEWER",
    ),
    ToolSpec(
        "get_chargeback_rate",
        "Chargeback rate for transactions in a period, optionally filtered by card type or region.",
        s.ChargebackRateArgs,
        "VIEWER",
    ),
    ToolSpec(
        "get_card_type_performance",
        "Credit versus debit approval and decline rates and approved volume, per currency.",
        s.CardTypePerformanceArgs,
        "VIEWER",
    ),
    ToolSpec(
        "get_transaction_volume_by_region",
        "Approved transaction volume and count by region and currency, optionally filtered by card type.",
        s.RegionVolumeArgs,
        "VIEWER",
    ),
    ToolSpec(
        "get_fraud_indicators",
        "Risk indicators (not confirmed fraud): flagged transaction counts by day and reason for a "
        "period, optionally filtered by card type.",
        s.FraudIndicatorsArgs,
        "ANALYST",
    ),
)


class ToolRegistry:
    def __init__(self, specs: tuple[ToolSpec, ...], disabled: frozenset[str]) -> None:
        names = [spec.name for spec in specs]
        if len(names) != len(set(names)):
            raise ValueError("duplicate tool names in registry")
        if NO_TOOL in names:
            raise ValueError("NO_TOOL is reserved")
        self._specs: dict[str, ToolSpec] = {}
        for spec in specs:
            effective = spec.enabled and spec.name not in disabled
            self._specs[spec.name] = ToolSpec(
                name=spec.name,
                description=spec.description,
                args_model=spec.args_model,
                min_role=spec.min_role,
                enabled=effective,
                json_schema=spec.args_model.model_json_schema(),
            )

    def get(self, name: str) -> ToolSpec | None:
        return self._specs.get(name)

    def enabled(self) -> list[ToolSpec]:
        return [spec for spec in self._specs.values() if spec.enabled]

    def enabled_for_role(self, role: str) -> list[ToolSpec]:
        rank = ROLE_RANK.get(role, 0)
        return [spec for spec in self.enabled() if ROLE_RANK[spec.min_role] <= rank]


def build_registry(disabled: frozenset[str] = frozenset()) -> ToolRegistry:
    return ToolRegistry(CAPABILITIES, disabled)
