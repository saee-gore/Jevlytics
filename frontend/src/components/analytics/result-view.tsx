"use client";

import { Badge, Card, CardContent } from "@/components/ui/primitives";
import { DonutDatum, GroupedBar, GroupedDatum, SimpleBar, StatusDonut } from "@/components/charts/charts";
import { ErrorState, EmptyState } from "@/components/states/states";
import { formatCount, formatMoney, formatRate, toNumber } from "@/lib/format";
import {
  isApprovedVolume,
  type AnalyticsData,
  type ChatResponse,
  type Filters,
  type SettlementByCurrency,
} from "@/lib/types";

const TOOL_LABELS: Record<string, string> = {
  get_transaction_volume: "Transaction volume",
  get_transaction_count: "Transaction count",
  get_decline_reasons: "Decline reasons",
  get_decline_rate: "Decline rate",
  get_settlement_volume: "Settlement volume",
  get_chargeback_rate: "Chargeback rate",
  get_card_type_performance: "Card type performance",
  get_transaction_volume_by_region: "Volume by region",
  get_fraud_indicators: "Risk indicators",
};

function FiltersLine({ filters }: { filters: Filters | null }) {
  if (!filters) return null;
  const parts: string[] = [];
  if (filters.date_range) parts.push(`${filters.date_range.start} to ${filters.date_range.end}`);
  for (const key of ["card_type", "card_network", "currency", "region"] as const) {
    const v = filters[key];
    if (v) parts.push(`${key.replace("_", " ")}: ${String(v)}`);
  }
  if (parts.length === 0) return null;
  return (
    <div className="flex flex-wrap gap-2 text-xs text-muted">
      <span className="font-medium text-ink">Applied filters:</span>
      {parts.map((p) => (
        <Badge key={p}>{p}</Badge>
      ))}
    </div>
  );
}

function Figures({ data }: { data: AnalyticsData }) {
  const rows: [string, string][] = [];
  if (data.transaction_count !== undefined) rows.push(["Transactions", formatCount(data.transaction_count)]);
  if (data.declined_count !== undefined) rows.push(["Declined", formatCount(data.declined_count)]);
  if (data.decline_rate !== undefined) rows.push(["Decline rate", formatRate(data.decline_rate)]);
  if (data.total_approved_count !== undefined) rows.push(["Approved", formatCount(data.total_approved_count)]);
  if (data.total_transaction_count !== undefined) rows.push(["Total transactions", formatCount(data.total_transaction_count)]);
  if (data.chargeback_count !== undefined) rows.push(["Chargebacks", formatCount(data.chargeback_count)]);
  if (data.chargeback_rate !== undefined) rows.push(["Chargeback rate", formatRate(data.chargeback_rate)]);
  if (data.flagged_count !== undefined) rows.push(["Flagged (risk indicators)", formatCount(data.flagged_count)]);
  if (data.flagged_rate !== undefined) rows.push(["Flagged rate", formatRate(data.flagged_rate)]);
  if (rows.length === 0) return null;
  return (
    <dl className="grid grid-cols-2 gap-x-6 gap-y-3 sm:grid-cols-3">
      {rows.map(([k, v]) => (
        <div key={k}>
          <dt className="text-xs text-muted">{k}</dt>
          <dd className="text-lg font-semibold text-ink">{v}</dd>
        </div>
      ))}
    </dl>
  );
}

function Table({ headers, rows }: { headers: string[]; rows: (string | number)[][] }) {
  return (
    <div className="overflow-x-auto">
      <table className="w-full text-left text-sm">
        <thead>
          <tr className="border-b border-line text-xs text-muted">
            {headers.map((h) => (
              <th key={h} className="px-2 py-2 font-medium">
                {h}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((r, i) => (
            <tr key={i} className="border-b border-line last:border-0">
              {r.map((cell, j) => (
                <td key={j} className="px-2 py-2 text-ink">
                  {cell}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}

/** Renders whatever structured data the backend returned. Charts only use single-unit series. */
function Breakdown({ data }: { data: AnalyticsData }) {
  const blocks: React.ReactNode[] = [];

  if (data.by_currency?.length) {
    const rows = data.by_currency;
    const single = new Set(rows.map((c) => c.currency)).size === 1;
    const approved = rows.filter(isApprovedVolume);
    const settled = rows.filter((c): c is SettlementByCurrency => !isApprovedVolume(c));
    blocks.push(
      <div key="cur" className="space-y-3">
        {approved.length > 0 ? (
          <Table
            headers={["Currency", "Approved count", "Approved volume"]}
            rows={approved.map((c) => [c.currency, formatCount(c.approved_count), formatMoney(c.approved_volume, c.currency)])}
          />
        ) : null}
        {settled.length > 0 ? (
          <Table
            headers={["Currency", "Settlements", "Settled transactions", "Settled volume"]}
            rows={settled.map((c) => [
              c.currency,
              formatCount(c.settlement_count),
              formatCount(c.settled_transaction_count),
              formatMoney(c.settled_volume, c.currency),
            ])}
          />
        ) : null}
        {single && approved.length > 0 ? (
          <SimpleBar
            data={approved.map((c) => ({ label: c.currency, value: toNumber(c.approved_volume) }))}
            valueLabel={`Approved volume (${approved[0].currency})`}
            format={(n) => n.toLocaleString("en-US")}
          />
        ) : null}
      </div>,
    );
  }

  if (data.by_status?.length) {
    blocks.push(
      <StatusDonut
        key="status"
        data={data.by_status.map<DonutDatum>((s) => ({ name: s.status, value: s.transaction_count }))}
      />,
    );
  }

  if (data.by_card_network?.length) {
    blocks.push(
      <div key="net" className="space-y-3">
        <Table
          headers={["Card network", "Transactions", "Declined", "Decline rate"]}
          rows={data.by_card_network.map((n) => [n.card_network, formatCount(n.transaction_count), formatCount(n.declined_count), formatRate(n.decline_rate)])}
        />
        <SimpleBar
          data={data.by_card_network.map((n) => ({ label: n.card_network, value: n.decline_rate ?? 0 }))}
          valueLabel="Decline rate"
          format={(n) => `${(n * 100).toFixed(0)}%`}
        />
      </div>,
    );
  }

  if (data.reasons?.length) {
    blocks.push(
      <div key="reasons" className="space-y-3">
        <Table
          headers={["Decline reason", "Declined", "Share of declines"]}
          rows={data.reasons.map((r) => [r.decline_reason, formatCount(r.declined_count), formatRate(r.share_of_declines)])}
        />
        <SimpleBar
          data={data.reasons.map((r) => ({ label: r.decline_reason, value: r.share_of_declines ?? 0 }))}
          valueLabel="Share of declines"
          format={(n) => `${(n * 100).toFixed(0)}%`}
        />
      </div>,
    );
  }

  if (data.by_card_type_and_currency?.length) {
    const currencies = new Set(data.by_card_type_and_currency.map((b) => b.currency));
    const single = currencies.size === 1;
    const cardTypes = Array.from(new Set(data.by_card_type_and_currency.map((b) => b.card_type)));
    const grouped: GroupedDatum[] = cardTypes.map((ct) => {
      const row = data.by_card_type_and_currency!.find((b) => b.card_type === ct);
      return { label: ct, rate: row?.decline_rate ?? 0 };
    });
    blocks.push(
      <div key="cards" className="space-y-3">
        <Table
          headers={["Card type", "Currency", "Approved", "Declined", "Decline rate", "Approved volume"]}
          rows={data.by_card_type_and_currency.map((b) => [
            b.card_type,
            b.currency,
            formatCount(b.approved_count),
            formatCount(b.declined_count),
            formatRate(b.decline_rate),
            formatMoney(b.approved_volume, b.currency),
          ])}
        />
        {single ? (
          <GroupedBar data={grouped} series={[{ key: "rate", label: "Decline rate" }]} format={(n) => `${(n * 100).toFixed(0)}%`} />
        ) : null}
      </div>,
    );
  }

  if (data.by_region_and_currency?.length) {
    blocks.push(
      <div key="region" className="space-y-3">
        <Table
          headers={["Region", "Currency", "Approved count", "Approved volume"]}
          rows={data.by_region_and_currency.map((r) => [r.region, r.currency, formatCount(r.approved_count), formatMoney(r.approved_volume, r.currency)])}
        />
      </div>,
    );
  }

  return blocks.length ? <div className="space-y-6">{blocks}</div> : null;
}

export function ResultView({ response, compact = false }: { response: ChatResponse; compact?: boolean }) {
  if (response.status === "temporarily_unavailable") {
    return <ErrorState message="Analytics is temporarily unavailable. Nothing was calculated or shown. Try again later." />;
  }
  if (response.status === "blocked" || response.status === "unsupported" || response.status === "clarification_required") {
    // The backend's wording is shown as returned. The frontend never overrides a backend rejection.
    return (
      <Card className="border-amber-200 bg-amber-50/40">
        <CardContent className="space-y-2 p-4 text-sm text-ink">
          <Badge tone={response.status === "clarification_required" ? "accent" : "warn"}>
            {response.status === "clarification_required"
              ? "Needs clarification"
              : response.status === "unsupported"
                ? "Out of scope"
                : "Not processed"}
          </Badge>
          <p>{response.answer ?? "No further detail is available."}</p>
        </CardContent>
      </Card>
    );
  }
  if (!response.data) {
    return <EmptyState title="No figures were returned for this question." />;
  }

  const label = response.tool_used ? TOOL_LABELS[response.tool_used] ?? response.tool_used : "Analytics";
  if (compact) {
    // Used inside dashboard panels, which already provide the title and card frame.
    return (
      <div className="space-y-4">
        <FiltersLine filters={response.filters ?? response.data.filters ?? null} />
        <Figures data={response.data} />
        <Breakdown data={response.data} />
      </div>
    );
  }
  return (
    <Card>
      <CardContent className="space-y-4 p-5">
        <div className="flex flex-wrap items-center gap-2">
          <Badge tone="accent">{label}</Badge>
          <span className="text-xs text-muted">Request {response.request_id}</span>
        </div>
        {response.answer ? <p className="text-sm text-ink">{response.answer}</p> : null}
        <FiltersLine filters={response.filters ?? response.data.filters ?? null} />
        <Figures data={response.data} />
        <Breakdown data={response.data} />
        {response.data.note || response.data.cohort_note ? (
          <p className="text-xs text-muted">{response.data.note ?? response.data.cohort_note}</p>
        ) : null}
      </CardContent>
    </Card>
  );
}
