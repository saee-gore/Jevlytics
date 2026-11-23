"""Parameterised, merchant-scoped SQL for the analytics layer.

Rules enforced here:
  * Every statement filters on :merchant_id. It is always the trusted value from the
    authenticated server context, never a value from the prompt or the LLM.
  * All user-influenced values are bound parameters. The only interpolated text is the
    constant BASE_WHERE fragment defined in this file.
  * Optional filters use the "(:param IS NULL OR column = :param)" pattern.
  * Queries return aggregates only. No statement selects raw customer or card-adjacent columns.
"""

from __future__ import annotations

# Shared predicate. Callers must always bind merchant_id, start_utc, end_utc and every optional
# filter (None when unused).
BASE_WHERE = """
    t.merchant_id = :merchant_id
    AND t.transaction_timestamp >= :start_utc
    AND t.transaction_timestamp < :end_utc
    AND (CAST(:card_type AS varchar) IS NULL OR t.card_type = CAST(:card_type AS varchar))
    AND (CAST(:card_network AS varchar) IS NULL OR t.card_network = CAST(:card_network AS varchar))
    AND (CAST(:currency AS varchar) IS NULL OR t.currency = CAST(:currency AS varchar))
    AND (CAST(:region AS varchar) IS NULL OR t.region = CAST(:region AS varchar))
    AND (CAST(:status AS varchar) IS NULL OR t.status = CAST(:status AS varchar))
"""

TRANSACTION_VOLUME_BY_CURRENCY = f"""
SELECT t.currency AS currency,
       COUNT(*) AS approved_count,
       COALESCE(SUM(t.amount), 0) AS approved_volume
FROM transactions t
WHERE {BASE_WHERE}
  AND t.status = 'APPROVED'
GROUP BY t.currency
ORDER BY t.currency
"""

TRANSACTION_COUNT_BY_STATUS = f"""
SELECT t.status AS status, COUNT(*) AS transaction_count
FROM transactions t
WHERE {BASE_WHERE}
GROUP BY t.status
ORDER BY t.status
"""

DECLINE_REASONS = f"""
SELECT COALESCE(t.decline_reason, 'UNSPECIFIED') AS decline_reason,
       COUNT(*) AS declined_count
FROM transactions t
WHERE {BASE_WHERE}
  AND t.status = 'DECLINED'
GROUP BY COALESCE(t.decline_reason, 'UNSPECIFIED')
ORDER BY declined_count DESC, decline_reason ASC
"""

DECLINE_COUNTS_BY_NETWORK = f"""
SELECT t.card_network AS card_network,
       COUNT(*) FILTER (WHERE t.status = 'APPROVED') AS approved_count,
       COUNT(*) FILTER (WHERE t.status = 'DECLINED') AS declined_count
FROM transactions t
WHERE {BASE_WHERE}
  AND t.status IN ('APPROVED', 'DECLINED')
GROUP BY t.card_network
ORDER BY t.card_network
"""

SETTLEMENT_VOLUME_BY_CURRENCY = """
SELECT s.currency AS currency,
       COUNT(*) AS settlement_count,
       COALESCE(SUM(s.gross_amount), 0) AS settled_volume,
       COALESCE(SUM(s.transaction_count), 0) AS settled_transaction_count
FROM settlements s
WHERE s.merchant_id = :merchant_id
  AND s.settlement_date >= :start_date
  AND s.settlement_date <= :end_date
  AND (CAST(:currency AS varchar) IS NULL OR s.currency = CAST(:currency AS varchar))
GROUP BY s.currency
ORDER BY s.currency
"""

APPROVED_COUNT = f"""
SELECT COUNT(*) AS approved_count
FROM transactions t
WHERE {BASE_WHERE}
  AND t.status = 'APPROVED'
"""

# Cohort numerator: chargebacks whose original transaction is in the period, with the same
# merchant on both rows (the composite FK already guarantees this; the join repeats it for clarity).
CHARGEBACKS_FOR_APPROVED_COHORT = f"""
SELECT COUNT(*) AS chargeback_count
FROM chargebacks c
JOIN transactions t
  ON t.transaction_id = c.transaction_id
 AND t.merchant_id = c.merchant_id
WHERE {BASE_WHERE}
  AND t.status = 'APPROVED'
"""

CARD_TYPE_PERFORMANCE = f"""
SELECT t.card_type AS card_type,
       t.currency AS currency,
       COUNT(*) FILTER (WHERE t.status = 'APPROVED') AS approved_count,
       COUNT(*) FILTER (WHERE t.status = 'DECLINED') AS declined_count,
       COALESCE(SUM(t.amount) FILTER (WHERE t.status = 'APPROVED'), 0) AS approved_volume
FROM transactions t
WHERE {BASE_WHERE}
  AND t.status IN ('APPROVED', 'DECLINED')
GROUP BY t.card_type, t.currency
ORDER BY t.card_type, t.currency
"""

VOLUME_BY_REGION = f"""
SELECT t.region AS region,
       t.currency AS currency,
       COUNT(*) AS approved_count,
       COALESCE(SUM(t.amount), 0) AS approved_volume
FROM transactions t
WHERE {BASE_WHERE}
  AND t.status = 'APPROVED'
GROUP BY t.region, t.currency
ORDER BY t.region, t.currency
"""

TOTAL_TRANSACTIONS = f"""
SELECT COUNT(*) AS transaction_count,
       COUNT(*) FILTER (WHERE t.risk_flag) AS flagged_count
FROM transactions t
WHERE {BASE_WHERE}
"""

FRAUD_INDICATORS_BY_DAY = f"""
SELECT CAST((t.transaction_timestamp AT TIME ZONE CAST(:tz AS varchar)) AS date) AS local_day,
       COALESCE(t.risk_reason, 'UNSPECIFIED') AS risk_reason,
       COUNT(*) AS flagged_count
FROM transactions t
WHERE {BASE_WHERE}
  AND t.risk_flag = TRUE
GROUP BY 1, 2
ORDER BY 1, 2
"""

MERCHANT_TIMEZONE = """
SELECT m.timezone AS timezone FROM merchants m WHERE m.merchant_id = :merchant_id
"""
