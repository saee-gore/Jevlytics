"use client";

import { useQueries, useQueryClient } from "@tanstack/react-query";
import { RefreshCw } from "lucide-react";
import { useEffect, useState } from "react";
import { ResultView } from "@/components/analytics/result-view";
import { KpiCard, StatusDonut, SimpleBar } from "@/components/charts/charts";
import { Button, Card, CardContent, CardHeader, CardTitle, Select } from "@/components/ui/primitives";
import { EmptyState, ErrorState, LoadingState } from "@/components/states/states";
import { ask } from "@/lib/data";
import { IS_MOCK } from "@/lib/config";
import { formatCount, formatMoney, formatRate, toNumber } from "@/lib/format";
import { recordActivity, readActivity, type ActivityEntry } from "@/lib/activity";
import { isApprovedVolume, type ChatResponse } from "@/lib/types";

const PERIODS = {
  "last month": "last month",
  "this quarter": "this quarter",
  "last 30 days": "in the last 30 days",
} as const;
type Period = keyof typeof PERIODS;

function overviewQueryOptions(key: string, question: string, enabled: boolean) {
  return {
    queryKey: ["overview", key, question],
    queryFn: async () => {
      const response = await ask(question);
      recordActivity({ question, status: response.status, tool: response.tool_used, requestId: response.request_id });
      return response;
    },
    enabled,
    retry: false,
  };
}

function Panel({ title, query, children }: { title: string; query: { isLoading: boolean; error: unknown; data?: ChatResponse }; children: (r: ChatResponse) => React.ReactNode }) {
  return (
    <Card>
      <CardHeader>
        <CardTitle>{title}</CardTitle>
      </CardHeader>
      <CardContent>
        {query.isLoading ? <LoadingState /> : null}
        {query.error ? <ErrorState message={(query.error as Error).message} /> : null}
        {query.data ? (query.data.status === "answered" && query.data.data ? children(query.data) : <ResultView response={query.data} />) : null}
        {!query.isLoading && !query.error && !query.data ? (
          <EmptyState title="Not loaded yet" body="Press Refresh to load this panel." />
        ) : null}
      </CardContent>
    </Card>
  );
}

function volumeText(r: ChatResponse): string {
  const rows = (r.data?.by_currency ?? []).filter(isApprovedVolume);
  if (rows.length === 0) return "—";
  return rows.map((c) => formatMoney(c.approved_volume, c.currency)).join(" · ");
}

export default function OverviewPage() {
  const [period, setPeriod] = useState<Period>("last month");
  const [refreshed, setRefreshed] = useState(false);
  const queryClient = useQueryClient();
  // Live mode makes one Jev and LLM call per question, so panels load only on Refresh.
  const enabled = IS_MOCK || refreshed;
  const p = PERIODS[period];

  const queries = useQueries({
    queries: [
      overview("volume", `What was our transaction volume ${p}?`, enabled),
      overview("count", `How many transactions did we process ${p}?`, enabled),
      overview("decline", `What was our decline rate ${p}?`, enabled),
      overview("chargeback", `What was our chargeback rate ${p}?`, enabled),
      overview("cards", `Compare credit and debit card performance ${p}.`, enabled),
      overview("region", `Show transaction volume by region ${p}.`, enabled),
    ],
  });
  const [volume, count, decline, chargeback, cards, region] = queries;

  const statusData = count.data?.data?.by_status?.map((s) => ({ name: s.status, value: s.transaction_count })) ?? [];
  const regionData =
    region.data?.data?.by_region_and_currency?.map((r) => ({ label: `${r.region} ${r.currency}`, value: toNumber(r.approved_volume) })) ?? [];

  return (
    <div className="space-y-6">
      <header className="flex flex-col gap-4 md:flex-row md:items-end md:justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Overview</h1>
          <p className="text-sm text-muted">
            Period: <span className="font-medium text-ink">{period}</span>
          </p>
        </div>
        <div className="flex items-center gap-2">
          <label className="sr-only" htmlFor="period">Date range</label>
          <Select id="period" value={period} onChange={(e) => setPeriod(e.target.value as Period)}>
            {(Object.keys(PERIODS) as Period[]).map((k) => (
              <option key={k} value={k}>
                {k}
              </option>
            ))}
          </Select>
          <Button
            variant="outline"
            onClick={() => {
              if (!refreshed) setRefreshed(true);
              else void queryClient.invalidateQueries({ queryKey: ["overview"] });
            }}
          >
            <RefreshCw className="h-4 w-4" aria-hidden /> Refresh
          </Button>
        </div>
      </header>

      {!IS_MOCK && !refreshed ? (
        <p className="text-sm text-muted">Press Refresh to load figures. Each refresh asks the assistant six questions.</p>
      ) : null}

      <section aria-label="Key metrics" className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <KpiCard label="Total transaction volume" value={volume.data ? volumeText(volume.data) : "—"} definition="Approved volume per currency. Currencies are never added together." />
        <KpiCard label="Total transaction count" value={count.data?.data?.total_transaction_count !== undefined ? formatCount(count.data.data.total_transaction_count) : "—"} definition="All transactions in the period, by status." />
        <KpiCard label="Decline rate" value={decline.data?.data?.decline_rate !== undefined ? formatRate(decline.data.data.decline_rate) : "—"} definition="Declined ÷ (approved + declined) for the period." />
        <KpiCard label="Chargeback rate" value={chargeback.data?.data?.chargeback_rate !== undefined ? formatRate(chargeback.data.data.chargeback_rate) : "—"} definition="Chargebacks ÷ approved transactions, matched to original approval date." />
      </section>

      <section className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        <Card className="lg:col-span-2">
          <CardHeader>
            <CardTitle>Transaction volume trend</CardTitle>
          </CardHeader>
          <CardContent>
            <EmptyState
              title="Trend data is not available"
              body="The current API has no time-series endpoint. A daily or weekly trend needs a backend endpoint that returns grouped volumes."
            />
          </CardContent>
        </Card>

        <Panel title="Transaction status breakdown" query={count}>
          {() => (statusData.length ? <StatusDonut data={statusData} /> : <EmptyState title="No status breakdown returned." />)}
        </Panel>

        <Panel title="Card type performance" query={cards}>
          {(r) => <ResultView response={{ ...r, answer: null }} compact />}
        </Panel>

        <Panel title="Volume by region" query={region}>
          {() => (regionData.length ? <SimpleBar data={regionData} valueLabel="Approved volume" format={(n) => n.toLocaleString("en-US")} /> : <EmptyState title="No regional data returned." />)}
        </Panel>

        <RecentActivity />
      </section>
    </div>
  );
}

function overview(key: string, question: string, enabled: boolean) {
  return overviewQueryOptions(key, question, enabled);
}

function RecentActivity() {
  const [entries, setEntries] = useState<ActivityEntry[]>([]);
  useEffect(() => setEntries(readActivity().slice(0, 6)), []);
  return (
    <Card>
      <CardHeader>
        <CardTitle>Recent analytics activity (this session)</CardTitle>
      </CardHeader>
      <CardContent>
        {entries.length === 0 ? (
          <EmptyState title="No questions asked yet in this session." />
        ) : (
          <ul className="divide-y divide-line text-sm">
            {entries.map((e) => (
              <li key={`${e.at}-${e.question}`} className="flex flex-col py-2">
                <span className="text-ink">{e.question}</span>
                <span className="text-xs text-muted">
                  {new Date(e.at).toLocaleString()} · {e.status}
                  {e.tool ? ` · ${e.tool}` : ""}
                </span>
              </li>
            ))}
          </ul>
        )}
      </CardContent>
    </Card>
  );
}
