// Transaction types for the Activity page. Two sources share one dashboard shape:
//   - live mode: GET /transactions and GET /transactions/summary (the API contract below)
//   - mock mode: the synthetic demo rows in demo-transactions.ts

export interface ApiTransaction {
  transaction_id: string;
  transaction_timestamp: string;
  card_type: string;
  card_network: string;
  amount: string;
  currency: string;
  status: string;
  decline_reason: string | null;
  region: string;
}

export interface TransactionListResponse {
  filters: Record<string, unknown>;
  total: number;
  limit: number;
  offset: number;
  transactions: ApiTransaction[];
  request_id: string;
}

export interface TransactionSummaryResponse {
  filters: Record<string, unknown>;
  by_status: { status: string; transaction_count: number }[];
  by_card_network: {
    card_network: string;
    transaction_count: number;
    approved_count: number;
    declined_count: number;
    decline_rate: number | null;
  }[];
  approved_volume_by_currency: { currency: string; approved_count: number; approved_volume: string }[];
  decline_rate: number | null;
  request_id: string;
}

/** One row as the table shows it. Demo rows (numeric amount) and API rows (string amount) both fit. */
export interface TransactionRow {
  id: string;
  at: string;
  cardType: string;
  network: string;
  amount: string | number;
  currency: string;
  status: string;
  declineReason: string | null;
  region: string;
}

export function rowFromApi(t: ApiTransaction): TransactionRow {
  return {
    id: t.transaction_id,
    at: t.transaction_timestamp,
    cardType: t.card_type,
    network: t.card_network,
    amount: t.amount,
    currency: t.currency,
    status: t.status,
    declineReason: t.decline_reason,
    region: t.region,
  };
}

/** Figures for the dashboard cards and charts. Currencies are never added together. */
export interface Dashboard {
  transactionCount: number;
  statusCounts: { name: string; value: number }[];
  networkCounts: { label: string; value: number }[];
  approvedByCurrency: { currency: string; amount: string | number }[];
  declined: number;
  declineRate: number | null;
}

export function dashboardFromSummary(s: TransactionSummaryResponse): Dashboard {
  const statusCounts = s.by_status.map((r) => ({ name: r.status, value: r.transaction_count }));
  const declined = s.by_status.find((r) => r.status === "DECLINED")?.transaction_count ?? 0;
  return {
    transactionCount: s.by_status.reduce((sum, r) => sum + r.transaction_count, 0),
    statusCounts,
    networkCounts: s.by_card_network
      .map((r) => ({ label: r.card_network, value: r.transaction_count }))
      .sort((a, b) => b.value - a.value),
    approvedByCurrency: s.approved_volume_by_currency.map((r) => ({
      currency: r.currency,
      amount: r.approved_volume,
    })),
    declined,
    declineRate: s.decline_rate,
  };
}

/** Same figures computed from demo rows, using the definition DECLINED ÷ (APPROVED + DECLINED). */
export function dashboardFromRows(rows: TransactionRow[]): Dashboard {
  const status = new Map<string, number>();
  const network = new Map<string, number>();
  const volume = new Map<string, number>();
  for (const t of rows) {
    status.set(t.status, (status.get(t.status) ?? 0) + 1);
    network.set(t.network, (network.get(t.network) ?? 0) + 1);
    if (t.status === "APPROVED") {
      volume.set(t.currency, (volume.get(t.currency) ?? 0) + Number(t.amount));
    }
  }
  const approved = status.get("APPROVED") ?? 0;
  const declined = status.get("DECLINED") ?? 0;
  const decisions = approved + declined;
  return {
    transactionCount: rows.length,
    statusCounts: Array.from(status, ([name, value]) => ({ name, value })),
    networkCounts: Array.from(network, ([label, value]) => ({ label, value })).sort((a, b) => b.value - a.value),
    approvedByCurrency: Array.from(volume, ([currency, amount]) => ({ currency, amount })),
    declined,
    declineRate: decisions > 0 ? declined / decisions : null,
  };
}
