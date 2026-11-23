// Typed mirror of the backend contract (app/orchestration/schemas.py and app/analytics/service.py).
// Only fields the backend actually returns are listed. Money values are strings from the backend;
// currencies are never summed or converted in the UI.

export type ResponseStatus =
  | "answered"
  | "clarification_required"
  | "unsupported"
  | "blocked"
  | "temporarily_unavailable";

export type Role = "ANALYST";

export interface DateRange {
  start: string;
  end: string;
}

export interface Filters {
  date_range?: DateRange;
  currency?: string | null;
  card_type?: string | null;
  card_network?: string | null;
  region?: string | null;
  [key: string]: unknown;
}

export interface ByCurrencyVolume {
  currency: string;
  approved_count: number;
  approved_volume: string;
}

/** Settlement rows also arrive under by_currency, with their own fields. */
export interface SettlementByCurrency {
  currency: string;
  settlement_count: number;
  settled_transaction_count: number;
  settled_volume: string;
}

export function isApprovedVolume(row: ByCurrencyVolume | SettlementByCurrency): row is ByCurrencyVolume {
  return "approved_volume" in row;
}

export interface ByStatus {
  status: string;
  transaction_count: number;
}

export interface ByCardNetwork {
  card_network: string;
  transaction_count: number;
  declined_count: number;
  decline_rate: number | null;
}

export interface DeclineReason {
  decline_reason: string;
  declined_count: number;
  share_of_declines: number | null;
}

export interface CardTypeBucket {
  card_type: string;
  currency: string;
  approved_count: number;
  declined_count: number;
  decline_rate: number | null;
  approved_volume: string;
}

export interface RegionBucket {
  region: string;
  currency: string;
  approved_count: number;
  approved_volume: string;
}

/** Shape of ChatResponse.data for the analytics tools. Fields depend on the tool used. */
export interface AnalyticsData {
  filters?: Filters;
  by_currency?: (ByCurrencyVolume | SettlementByCurrency)[];
  total_approved_count?: number;
  by_status?: ByStatus[];
  total_transaction_count?: number;
  transaction_count?: number;
  declined_count?: number;
  decline_rate?: number | null;
  by_card_network?: ByCardNetwork[];
  total_declined?: number;
  reasons?: DeclineReason[];
  by_card_type_and_currency?: CardTypeBucket[];
  by_region_and_currency?: RegionBucket[];
  approved_transaction_count?: number;
  chargeback_count?: number;
  chargeback_rate?: number | null;
  cohort_note?: string;
  note?: string;
  flagged_count?: number;
  flagged_rate?: number | null;
  [key: string]: unknown;
}

export interface ChatResponse {
  status: ResponseStatus;
  answer: string | null;
  tool_used: string | null;
  filters: Filters | null;
  data: AnalyticsData | null;
  chart: Record<string, unknown> | null;
  request_id: string;
}

export interface CapabilityItem {
  name: string;
  description: string;
  min_role: string;
}

export interface CapabilitiesResponse {
  role: Role;
  capabilities: CapabilityItem[];
  request_id: string;
}

export interface HealthResponse {
  status: "ok" | "degraded";
  database: "ok" | "unavailable";
  configured?: { auth: boolean; jev: boolean; llm: boolean };
}

export class ApiError extends Error {
  constructor(
    message: string,
    public readonly httpStatus: number,
  ) {
    super(message);
    this.name = "ApiError";
  }
}
