"use client";

import { useMutation, useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { ResultView } from "@/components/analytics/result-view";
import { Button, Card, CardContent, CardHeader, CardTitle, Input, Select } from "@/components/ui/primitives";
import { ErrorState, LoadingState } from "@/components/states/states";
import { recordActivity } from "@/lib/activity";
import { ask, getCapabilities } from "@/lib/data";
import type { ChatResponse } from "@/lib/types";

// Phrasing used to ask each capability. The backend resolves the question, so these are text, not a
// structured request. Only the date range is offered: the API has no structured filter contract yet.
const PHRASES: Record<string, string> = {
  get_transaction_volume: "What was our transaction volume",
  get_transaction_count: "How many transactions did we process",
  get_decline_reasons: "What were the most common decline reasons",
  get_decline_rate: "What was our decline rate",
  get_settlement_volume: "How much transaction volume was settled",
  get_chargeback_rate: "What was our chargeback rate",
  get_card_type_performance: "Compare credit and debit card performance",
  get_transaction_volume_by_region: "Show transaction volume by region",
  get_fraud_indicators: "Show the risk indicators",
};

export default function AnalyticsPage() {
  const capabilities = useQuery({ queryKey: ["capabilities"], queryFn: getCapabilities, retry: false });
  const [capability, setCapability] = useState("get_transaction_volume");
  const [start, setStart] = useState("2026-10-01");
  const [end, setEnd] = useState("2026-10-31");
  const [result, setResult] = useState<ChatResponse | null>(null);

  const run = useMutation({
    mutationFn: async () => {
      const question = `${PHRASES[capability] ?? "Show analytics for"} from ${start} to ${end}?`;
      const response = await ask(question);
      recordActivity({ question, status: response.status, tool: response.tool_used, requestId: response.request_id });
      return response;
    },
    onSuccess: setResult,
    onError: () => setResult(null),
  });

  const available = capabilities.data?.capabilities.filter((c) => PHRASES[c.name]) ?? [];
  const validRange = start !== "" && end !== "" && start <= end;

  function reset() {
    setStart("2026-10-01");
    setEnd("2026-10-31");
    setResult(null);
    run.reset();
  }

  return (
    <div className="space-y-6">
      <header>
        <h1 className="text-2xl font-semibold">Analytics</h1>
        <p className="text-sm text-muted">Explore one capability at a time. Results are aggregates only.</p>
      </header>

      <div className="grid grid-cols-1 gap-6 lg:grid-cols-[320px_1fr]">
        <Card>
          <CardHeader>
            <CardTitle>Capability and date range</CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            {capabilities.isLoading ? <LoadingState label="Loading capabilities…" /> : null}
            {capabilities.error ? <ErrorState message={(capabilities.error as Error).message} /> : null}
            <div className="space-y-1">
              <label htmlFor="capability" className="text-xs font-medium text-muted">Capability</label>
              <Select id="capability" className="w-full" value={capability} onChange={(e) => setCapability(e.target.value)}>
                {available.map((c) => (
                  <option key={c.name} value={c.name}>
                    {c.name}
                  </option>
                ))}
              </Select>
            </div>
            <div className="grid grid-cols-2 gap-3">
              <div className="space-y-1">
                <label htmlFor="start" className="text-xs font-medium text-muted">From</label>
                <Input id="start" type="date" value={start} onChange={(e) => setStart(e.target.value)} />
              </div>
              <div className="space-y-1">
                <label htmlFor="end" className="text-xs font-medium text-muted">To</label>
                <Input id="end" type="date" value={end} onChange={(e) => setEnd(e.target.value)} />
              </div>
            </div>
            {!validRange ? <p className="text-xs text-danger">Choose a start date on or before the end date.</p> : null}
            <div className="flex gap-2">
              <Button onClick={() => run.mutate()} disabled={!validRange || run.isPending || available.length === 0}>
                Run
              </Button>
              <Button variant="outline" onClick={reset}>
                Reset filters
              </Button>
            </div>
            <p className="text-xs text-muted">CSV export is not offered: the API does not provide one yet.</p>
          </CardContent>
        </Card>

        <section aria-label="Result" className="space-y-4">
          {run.isPending ? <LoadingState label="Retrieving figures…" /> : null}
          {run.error ? <ErrorState message={(run.error as Error).message} /> : null}
          {result ? <ResultView response={result} /> : null}
          {!result && !run.isPending && !run.error ? (
            <Card>
              <CardContent className="p-6 text-sm text-muted">Choose a capability and date range, then press Run.</CardContent>
            </Card>
          ) : null}
        </section>
      </div>
    </div>
  );
}
