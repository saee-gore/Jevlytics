// DEMO DATA ONLY. Fictional figures for the three seeded demo merchants. Never shown as live data:
// every screen that uses this module displays the "Demo data" label.
import { newRequestId } from "./ids";
import type {
  CapabilitiesResponse,
  ChatResponse,
  HealthResponse,
  ResponseStatus,
} from "./types";

export const DEMO_MERCHANTS = [
  { id: "merchant_001", name: "Retail / E-commerce (demo)" },
  { id: "merchant_002", name: "Subscription Services (demo)" },
  { id: "merchant_003", name: "Travel / Hospitality (demo)" },
] as const;

const DEMO_FILTERS = { date_range: { start: "2026-10-01", end: "2026-10-31" } };

function reply(
  status: ResponseStatus,
  answer: string | null,
  tool: string | null = null,
  data: ChatResponse["data"] = null,
): ChatResponse {
  return {
    status,
    answer,
    tool_used: tool,
    filters: tool ? DEMO_FILTERS : null,
    data: status === "answered" ? data : null,
    chart: null,
    request_id: newRequestId(),
  };
}

const MERCHANT_REFERENCE = /\bmerchant[\s_-]*(\d+|one|two|three|four|five|six|seven|eight|nine|ten)\b/gi;

/** Same rule as the backend screen (app/orchestration/merchant_refs.py): naming another merchant is refused. */
const NUMBER_WORDS: Record<string, number> = {
  one: 1, two: 2, three: 3, four: 4, five: 5, six: 6, seven: 7, eight: 8, nine: 9, ten: 10,
};

function namesOtherMerchant(message: string, callerMerchantId: string): boolean {
  const own = Number(callerMerchantId.replace(/\D/g, ""));
  for (const match of message.matchAll(MERCHANT_REFERENCE)) {
    const token = match[1].toLowerCase();
    const number = /^\d+$/.test(token) ? Number(token) : NUMBER_WORDS[token];
    if (number !== own) return true;
  }
  return /\b(?:other|another|different)[\s_-]+merchants?\b/i.test(message);
}

/** Keyword routing for the demo only. The live system uses Jev and the policy engine instead. */
export function mockAsk(message: string, callerMerchantId: string = DEMO_MERCHANTS[0].id): Promise<ChatResponse> {
  const q = message.toLowerCase();
  const response = (() => {
    if (namesOtherMerchant(message, callerMerchantId)) {
      return reply("blocked", `You can only ask about your own merchant data (${callerMerchantId}). That request names another merchant, so it cannot be processed.`);
    }
    if (/ignore (your|all|previous)|system prompt|api key|password|secret/.test(q)) {
      return reply("blocked", "That request cannot be processed.");
    }
    if (/refund|transfer|payout|move (the )?money|cancel|change the/.test(q)) {
      return reply("unsupported", "That request is outside the supported payment analytics capabilities. I can help you analyze transaction volume, decline rates, settlements, chargebacks, and other available metrics.");
    }
    if (/card number|cvv|pan\b/.test(q)) {
      return reply("blocked", "That request cannot be processed because it involves restricted or sensitive payment information.");
    }
    if (/decline rate/.test(q) && /network|visa|mastercard|amex/.test(q)) {
      return reply("answered", "Decline rate by card network for October (demo data).", "get_decline_rate", {
        filters: DEMO_FILTERS,
        transaction_count: 8120,
        declined_count: 412,
        decline_rate: 0.0507,
        by_card_network: [
          { card_network: "VISA", transaction_count: 4870, declined_count: 221, decline_rate: 0.0454 },
          { card_network: "MASTERCARD", transaction_count: 2310, declined_count: 139, decline_rate: 0.0602 },
          { card_network: "AMEX", transaction_count: 940, declined_count: 52, decline_rate: 0.0553 },
        ],
      });
    }
    if (/decline/.test(q) && /reason/.test(q)) {
      return reply("answered", "Most common decline reasons for October (demo data).", "get_decline_reasons", {
        filters: DEMO_FILTERS,
        total_declined: 412,
        reasons: [
          { decline_reason: "INSUFFICIENT_FUNDS", declined_count: 150, share_of_declines: 0.364 },
          { decline_reason: "DO_NOT_HONOR", declined_count: 118, share_of_declines: 0.286 },
          { decline_reason: "EXPIRED_CARD", declined_count: 89, share_of_declines: 0.216 },
          { decline_reason: "OTHER", declined_count: 55, share_of_declines: 0.134 },
        ],
      });
    }
    if (/credit|debit/.test(q)) {
      return reply("answered", "Credit and debit performance for October (demo data).", "get_card_type_performance", {
        filters: DEMO_FILTERS,
        by_card_type_and_currency: [
          { card_type: "CREDIT", currency: "USD", approved_count: 3900, declined_count: 260, decline_rate: 0.0625, approved_volume: "412300.55" },
          { card_type: "DEBIT", currency: "USD", approved_count: 3300, declined_count: 152, decline_rate: 0.0440, approved_volume: "265120.10" },
        ],
      });
    }
    if (/region/.test(q)) {
      return reply("answered", "Transaction volume by region for October (demo data). Currencies are shown separately.", "get_transaction_volume_by_region", {
        filters: DEMO_FILTERS,
        by_region_and_currency: [
          { region: "US-WEST", currency: "USD", approved_count: 2900, approved_volume: "301220.00" },
          { region: "US-EAST", currency: "USD", approved_count: 2400, approved_volume: "244010.40" },
          { region: "UK", currency: "GBP", approved_count: 1100, approved_volume: "98210.75" },
        ],
      });
    }
    if (/settle/.test(q)) {
      return reply("answered", "Settled volume for October (demo data).", "get_settlement_volume", {
        filters: DEMO_FILTERS,
        by_currency: [{ currency: "USD", settlement_count: 42, settled_transaction_count: 3100, settled_volume: "512300.00" }],
      });
    }
    if (/chargeback/.test(q)) {
      return reply("answered", "Chargeback rate for October (demo data).", "get_chargeback_rate", {
        filters: DEMO_FILTERS,
        approved_transaction_count: 7200,
        chargeback_count: 36,
        chargeback_rate: 0.005,
        cohort_note: "Chargebacks are matched to the transaction date of the original approval.",
      });
    }
    if (/fraud|risk|unusual/.test(q)) {
      return reply("answered", "Risk indicators for October (demo data). These are not confirmed fraud.", "get_fraud_indicators", {
        filters: DEMO_FILTERS,
        note: "Risk indicators from scoring rules. These are not confirmed fraud.",
        transaction_count: 8120,
        flagged_count: 94,
        flagged_rate: 0.0116,
      });
    }
    if (/how many|count/.test(q)) {
      return reply("answered", "Transaction count by status for October (demo data).", "get_transaction_count", {
        filters: DEMO_FILTERS,
        by_status: [
          { status: "APPROVED", transaction_count: 7708 },
          { status: "DECLINED", transaction_count: 412 },
        ],
        total_transaction_count: 8120,
      });
    }
    if (/decline rate|decline/.test(q)) {
      return reply("answered", "Decline rate for October (demo data).", "get_decline_rate", {
        filters: DEMO_FILTERS,
        transaction_count: 8120,
        declined_count: 412,
        decline_rate: 0.0507,
      });
    }
    if (/volume|transactions|process/.test(q)) {
      return reply("answered", "Approved transaction volume for October (demo data). Currencies are shown separately.", "get_transaction_volume", {
        filters: DEMO_FILTERS,
        by_currency: [
          { currency: "USD", approved_count: 6200, approved_volume: "677430.55" },
          { currency: "GBP", approved_count: 1100, approved_volume: "98210.75" },
        ],
        total_approved_count: 7300,
      });
    }
    return reply(
      "clarification_required",
      "Which measure and period would you like? For example: volume, decline rate, settlements, chargebacks, or card type performance, for a month or quarter.",
    );
  })();
  return new Promise((resolve) => setTimeout(() => resolve(response), 350));
}

export const MOCK_CAPABILITIES: CapabilitiesResponse = {
  role: "ANALYST",
  request_id: "demo",
  capabilities: [
    { name: "get_transaction_volume", description: "Total approved transaction volume and count per currency, optionally filtered by card type, card network or currency.", min_role: "ANALYST" },
    { name: "get_transaction_count", description: "Transaction counts by status for a period, optionally filtered by card type, card network or status.", min_role: "ANALYST" },
    { name: "get_decline_reasons", description: "Most common decline reasons and their counts for a period, optionally filtered by card type or card network.", min_role: "ANALYST" },
    { name: "get_decline_rate", description: "Decline rate for a period, optionally filtered by card type or card network. Includes a breakdown by card network when no network filter is given.", min_role: "ANALYST" },
    { name: "get_settlement_volume", description: "Settled volume and settlement counts per currency for a period.", min_role: "ANALYST" },
    { name: "get_chargeback_rate", description: "Chargeback rate for transactions in a period, optionally filtered by card type or region.", min_role: "ANALYST" },
    { name: "get_card_type_performance", description: "Credit versus debit approval and decline rates and approved volume, per currency.", min_role: "ANALYST" },
    { name: "get_transaction_volume_by_region", description: "Approved transaction volume and count by region and currency, optionally filtered by card type.", min_role: "ANALYST" },
    { name: "get_fraud_indicators", description: "Risk indicators (not confirmed fraud): flagged transaction counts by day and reason for a period, optionally filtered by card type.", min_role: "ANALYST" },
  ],
};

export const MOCK_HEALTH: HealthResponse = {
  status: "ok",
  database: "ok",
  configured: { auth: true, jev: true, llm: true },
};
