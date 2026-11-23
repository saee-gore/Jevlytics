"""Metric helpers and the documented definition of every analytics metric.

Conventions (applied consistently by app/analytics/service.py):
  * Money is Decimal end to end and serialised as a fixed-point string with 2 decimals.
  * Rates are Decimal quantised to 4 decimal places (0.0625 = 6.25%). A rate with a zero
    denominator is None, never 0 and never an exception.
  * Currencies are never summed together. Every money figure is reported per ISO currency code.
  * Date ranges are inclusive calendar dates in the MERCHANT'S timezone. They are converted to a
    half-open UTC interval [start 00:00 local, end+1 00:00 local) so that DST and midnight
    boundaries are handled by zoneinfo, not by string comparison.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
from datetime import UTC, date, datetime, time, timedelta
from decimal import ROUND_HALF_EVEN, Decimal
from zoneinfo import ZoneInfo

RATE_QUANTUM = Decimal("0.0001")
MONEY_QUANTUM = Decimal("0.01")


def safe_rate(numerator: int, denominator: int) -> Decimal | None:
    """numerator / denominator, quantised to 4 dp. Returns None when the denominator is zero."""
    if denominator <= 0:
        return None
    return (Decimal(numerator) / Decimal(denominator)).quantize(RATE_QUANTUM, rounding=ROUND_HALF_EVEN)


def money_str(value: Decimal | int | None) -> str:
    """Fixed-point string with two decimals. None or missing values become '0.00'."""
    if value is None:
        return "0.00"
    return str(Decimal(value).quantize(MONEY_QUANTUM, rounding=ROUND_HALF_EVEN))


def rate_float(value: Decimal | None) -> float | None:
    """JSON presentation of a rate. Calculation stays Decimal; only the response is float."""
    return None if value is None else float(value)


def local_window_to_utc(tz_name: str, start: date, end: date) -> tuple[datetime, datetime]:
    """Inclusive local dates [start, end] -> half-open UTC interval [start_utc, end_utc)."""
    if end < start:
        raise ValueError("end must not be before start")
    tz = ZoneInfo(tz_name)
    start_local = datetime.combine(start, time.min, tzinfo=tz)
    end_local = datetime.combine(end + timedelta(days=1), time.min, tzinfo=tz)
    return start_local.astimezone(UTC), end_local.astimezone(UTC)


@dataclass(frozen=True)
class MetricDefinition:
    tool: str
    formula: str
    filters: str
    date_semantics: str
    assumptions: str
    zero_denominator: str


METRIC_DEFINITIONS: dict[str, MetricDefinition] = {
    "get_transaction_volume": MetricDefinition(
        tool="get_transaction_volume",
        formula="Sum of amount over transactions with status APPROVED, grouped by currency.",
        filters="card_type, card_network, currency (optional). Status is fixed to APPROVED.",
        date_semantics="transaction_timestamp in the merchant timezone, inclusive dates.",
        assumptions=(
            "Gross approved volume. Refunded and reversed transactions are excluded because their "
            "status is no longer APPROVED. Net volume (after refunds) is not computed in this version."
        ),
        zero_denominator="Not applicable. Empty result returns an empty currency list.",
    ),
    "get_transaction_count": MetricDefinition(
        tool="get_transaction_count",
        formula="Count of transactions grouped by status (all statuses unless status is given).",
        filters="card_type, card_network, status (optional).",
        date_semantics="transaction_timestamp in the merchant timezone, inclusive dates.",
        assumptions="Counts are of transaction records, not of distinct cards or customers.",
        zero_denominator="Not applicable. Totals of zero are reported as 0.",
    ),
    "get_decline_reasons": MetricDefinition(
        tool="get_decline_reasons",
        formula="Count of DECLINED transactions grouped by decline_reason; share = count / total declined.",
        filters="card_type, card_network (optional). Status is fixed to DECLINED.",
        date_semantics="transaction_timestamp in the merchant timezone, inclusive dates.",
        assumptions="Declines without a recorded reason are reported as UNSPECIFIED.",
        zero_denominator="Share is None when there are no declines.",
    ),
    "get_decline_rate": MetricDefinition(
        tool="get_decline_rate",
        formula=(
            "decline_rate = DECLINED / (APPROVED + DECLINED). PENDING, REVERSED and REFUNDED are "
            "excluded from the denominator because they are not authorisation outcomes."
        ),
        filters=(
            "card_type, card_network (optional). When card_network is not set, "
            "a per-network breakdown is also returned."
        ),
        date_semantics="transaction_timestamp in the merchant timezone, inclusive dates.",
        assumptions="Rates are per transaction count, not per amount.",
        zero_denominator="decline_rate and per-network rates are None when APPROVED + DECLINED is zero.",
    ),
    "get_settlement_volume": MetricDefinition(
        tool="get_settlement_volume",
        formula="Sum of settlements.gross_amount grouped by currency.",
        filters="currency (optional).",
        date_semantics="settlements.settlement_date (merchant-local calendar date), inclusive.",
        assumptions=(
            "Settlements are gross of any fees. Settlement is reported per currency and never converted."
        ),
        zero_denominator="Not applicable. Empty result returns an empty currency list.",
    ),
    "get_chargeback_rate": MetricDefinition(
        tool="get_chargeback_rate",
        formula=(
            "chargeback_rate = chargebacks whose ORIGINAL transaction is in the period / APPROVED "
            "transactions in the period (cohort by transaction date)."
        ),
        filters="card_type, region (optional).",
        date_semantics=(
            "Cohort by transaction_timestamp in the merchant timezone. A chargeback raised after "
            "the period end still counts if its original transaction is in the period."
        ),
        assumptions="Count-based rate. The chargeback amount is not used in the rate.",
        zero_denominator="chargeback_rate is None when there are no APPROVED transactions in the period.",
    ),
    "get_card_type_performance": MetricDefinition(
        tool="get_card_type_performance",
        formula=(
            "Per (card_type, currency): approved_count, declined_count, decline_rate = declined / "
            "(approved + declined), approved_volume = sum of APPROVED amounts."
        ),
        filters="currency (optional).",
        date_semantics="transaction_timestamp in the merchant timezone, inclusive dates.",
        assumptions="Each currency is reported separately; rates are per currency bucket.",
        zero_denominator="decline_rate is None when approved + declined is zero for a bucket.",
    ),
    "get_transaction_volume_by_region": MetricDefinition(
        tool="get_transaction_volume_by_region",
        formula="Per (region, currency): count and sum of amount over APPROVED transactions.",
        filters="card_type (optional).",
        date_semantics="transaction_timestamp in the merchant timezone, inclusive dates.",
        assumptions="Region is the transaction's recorded region, not the cardholder's address.",
        zero_denominator="Not applicable. Empty result returns an empty list.",
    ),
    "get_fraud_indicators": MetricDefinition(
        tool="get_fraud_indicators",
        formula=(
            "Count of transactions with risk_flag = true, by merchant-local day and risk_reason, "
            "plus flagged_rate = flagged / total transactions."
        ),
        filters="card_type (optional).",
        date_semantics="Local day in the merchant timezone, inclusive dates.",
        assumptions=(
            "These are RISK INDICATORS produced by synthetic scoring rules. They are not confirmed "
            "fraud and must not be described as such."
        ),
        zero_denominator="flagged_rate is None when there are no transactions in the period.",
    ),
}


def definition_as_dict(tool: str) -> dict[str, str]:
    return asdict(METRIC_DEFINITIONS[tool])
