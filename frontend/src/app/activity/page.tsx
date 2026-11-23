"use client";

import { useQuery, useQueryClient } from "@tanstack/react-query";
import { Activity as ActivityIcon, KeyRound, ListFilter, PieChart as PieIcon, BarChart3, History } from "lucide-react";
import { useEffect, useMemo, useState } from "react";
import { ChatWidget } from "@/components/assistant/chat-panel";
import { KpiCard, SimpleBar, StatusDonut } from "@/components/charts/charts";
import { ErrorState, LoadingState } from "@/components/states/states";
import { Button, Input, Select } from "@/components/ui/primitives";
import { getStoredToken, liveTransactionSummary, liveTransactions, setStoredToken } from "@/lib/api";
import { IS_MOCK } from "@/lib/config";
import type { DemoTransaction } from "@/lib/demo-types";
import { formatCount, formatMoney, formatRate } from "@/lib/format";
import {
  dashboardFromRows,
  dashboardFromSummary,
  rowFromApi,
  type Dashboard,
  type TransactionRow,
} from "@/lib/transactions";
import { DEFAULT_USER, TOKEN_CHANGED_EVENT, USER_CHANGED_EVENT, getActiveUser, type DemoUser } from "@/lib/users";
import { cn } from "@/lib/utils";

const STATUSES = ["ALL", "APPROVED", "DECLINED", "PENDING", "REFUNDED", "REVERSED"] as const;

const STATUS_PILL: Record<string, string> = {
  APPROVED: "bg-ok/10 text-ok ring-ok/25",
  DECLINED: "bg-danger/10 text-danger ring-danger/25",
  PENDING: "bg-amber/15 text-warn ring-amber/30",
  REFUNDED: "bg-sky/10 text-sky ring-sky/25",
  REVERSED: "bg-violet/10 text-violet ring-violet/25",
};

const PAGE_SIZE = 50;
const DEMO_FIRST_DAY = "2026-07-01"; // the demo dataset starts on 2026-07-24
const MAX_ROWS = 100; // the API's maximum page size

/** YYYY-MM-DD in the browser's local calendar. */
function localDay(offsetDays: number): string {
  const d = new Date();
  d.setDate(d.getDate() + offsetDays);
  return d.toLocaleDateString("en-CA");
}

function shortTime(iso: string): string {
  // Wall-clock text as stored, so server and browser render the same characters.
  return iso.slice(0, 16).replace("T", " ");
}

/** A rounded card with a coloured icon chip and a heading. Used for each section. */
function Section({
  icon: Icon,
  title,
  hint,
  tone,
  children,
  className,
}: {
  icon: typeof ActivityIcon;
  title: string;
  hint?: string;
  tone: string;
  children: React.ReactNode;
  className?: string;
}) {
  return (
    <section className={cn("overflow-hidden rounded-2xl bg-surface shadow-card ring-1 ring-line", className)}>
      <header className="flex shrink-0 items-center gap-3 border-b border-line px-5 py-3">
        <span className={cn("flex h-8 w-8 items-center justify-center rounded-xl", tone)}>
          <Icon className="h-4 w-4" aria-hidden />
        </span>
        <div className="min-w-0 flex-1">
          <h2 className="text-sm font-semibold text-ink">{title}</h2>
          {hint ? <p className="text-xs text-muted">{hint}</p> : null}
        </div>
      </header>
      {children}
    </section>
  );
}

export default function ActivityPage() {
  const queryClient = useQueryClient();

  // Browser-only state (sessionStorage, dates) is read after mount to avoid hydration mismatches.
  const [hasToken, setHasToken] = useState(false);
  const [activeUser, setActiveUser] = useState<DemoUser>(DEFAULT_USER);
  const [tokenDraft, setTokenDraft] = useState("");
  const [start, setStart] = useState("");
  const [end, setEnd] = useState("");
  const [status, setStatus] = useState<(typeof STATUSES)[number]>("ALL");
  const [limit, setLimit] = useState(PAGE_SIZE);

  useEffect(() => {
    setStart(IS_MOCK ? DEMO_FIRST_DAY : localDay(-29));
    setEnd(localDay(0));
    const syncToken = () => setHasToken(Boolean(getStoredToken()));
    const syncUser = () => setActiveUser(getActiveUser());
    syncToken();
    syncUser();
    window.addEventListener(TOKEN_CHANGED_EVENT, syncToken);
    window.addEventListener(USER_CHANGED_EVENT, syncUser);
    return () => {
      window.removeEventListener(TOKEN_CHANGED_EVENT, syncToken);
      window.removeEventListener(USER_CHANGED_EVENT, syncUser);
    };
  }, []);

  // Demo data (demo mode only): the full synthetic dataset, loaded once from /public. Each user sees their merchant.
  const demoQuery = useQuery({
    queryKey: ["demo-transactions"],
    queryFn: async () => {
      const res = await fetch("/demo/transactions.json");
      if (!res.ok) throw new Error("Demo data could not be loaded.");
      return (await res.json()) as Record<string, DemoTransaction[]>;
    },
    enabled: IS_MOCK,
    staleTime: Infinity,
  });
  const allDemoRows = demoQuery.data?.[activeUser.merchantId] ?? [];

  const liveReady = !IS_MOCK && hasToken && start !== "" && end !== "";

  const summaryQuery = useQuery({
    queryKey: ["tx-summary", start, end],
    queryFn: () => liveTransactionSummary(start, end),
    enabled: liveReady,
    retry: false,
  });
  const listQuery = useQuery({
    queryKey: ["tx-list", start, end, status, limit],
    queryFn: () => liveTransactions({ start, end, status, limit }),
    enabled: liveReady,
    retry: false,
  });

  // Demo rows in the chosen dates (local calendar days), then by status for the table.
  const dateRows = useMemo(
    () => allDemoRows.filter((t) => t.at.slice(0, 10) >= start && t.at.slice(0, 10) <= end),
    [allDemoRows, start, end],
  );
  const demoFiltered = useMemo(
    () => dateRows.filter((t) => status === "ALL" || t.status === status),
    [dateRows, status],
  );

  let dashboard: Dashboard | null = null;
  let rows: TransactionRow[] = [];
  let matching = 0;
  if (IS_MOCK) {
    dashboard = dashboardFromRows(dateRows);
    rows = demoFiltered.slice(0, limit);
    matching = demoFiltered.length;
  } else if (summaryQuery.data) {
    dashboard = dashboardFromSummary(summaryQuery.data);
    rows = (listQuery.data?.transactions ?? []).map(rowFromApi);
    matching = listQuery.data?.total ?? 0;
  }
  const canLoadMore = rows.length < matching && (IS_MOCK || limit < MAX_ROWS);

  function saveToken() {
    const token = tokenDraft.trim();
    if (!token) return;
    setStoredToken(token);
    setTokenDraft("");
    setHasToken(true);
    void queryClient.invalidateQueries({ queryKey: ["tx-summary"] });
    void queryClient.invalidateQueries({ queryKey: ["tx-list"] });
  }

  const subtitle = IS_MOCK
    ? "Recent transactions and a basic dashboard. Demo data only."
    : "Transactions for your merchant, read from the analytics service.";

  const needsToken = !IS_MOCK && !hasToken;

  return (
    <div className="mx-auto flex h-full min-h-0 w-full max-w-6xl flex-col gap-3">
      {/* Hero */}
      <header className="relative shrink-0 overflow-hidden rounded-3xl bg-brand px-5 py-3 text-white shadow-glow">
        <div className="pointer-events-none absolute -right-16 -top-16 h-56 w-56 rounded-full bg-white/10" aria-hidden />
        <div className="pointer-events-none absolute -bottom-20 right-24 h-48 w-48 rounded-full bg-white/10" aria-hidden />
        <div className="relative flex flex-wrap items-end justify-between gap-4">
          <div className="space-y-1.5">
            <p className="text-xs font-semibold uppercase tracking-widest text-white/75">Payment analytics</p>
            <h1 className="text-xl font-bold tracking-tight">Activity</h1>
            <p className="max-w-xl text-sm text-white/85">{subtitle}</p>
          </div>
          <div className="rounded-2xl bg-white/15 px-4 py-2.5 text-sm ring-1 ring-white/25 backdrop-blur">
            <p className="font-semibold">{activeUser.displayName}</p>
            <p className="text-xs text-white/80">
              {activeUser.merchantId} · Analyst
            </p>
          </div>
        </div>
      </header>

      {needsToken ? (
        <section className="shrink-0 overflow-hidden rounded-2xl bg-amber-soft p-4 shadow-card ring-1 ring-amber/25">
          <div className="flex flex-col gap-4 md:flex-row md:items-center">
            <div className="flex items-start gap-3 md:flex-1">
              <span className="flex h-9 w-9 shrink-0 items-center justify-center rounded-xl bg-amber text-white">
                <KeyRound className="h-4 w-4" aria-hidden />
              </span>
              <div>
                <p className="text-sm font-semibold text-ink">Enter the access token for {activeUser.displayName}</p>
                <p className="text-sm text-muted">
                  The token for the selected user lets this page read that merchant&apos;s transactions. It is kept in this
                  browser tab only. Switch user in the sidebar to use a different token.
                </p>
              </div>
            </div>
            <form
              className="flex w-full flex-col gap-2 sm:flex-row md:w-auto"
              onSubmit={(e) => {
                e.preventDefault();
                saveToken();
              }}
            >
              <label className="sr-only" htmlFor="access-token">Access token</label>
              <Input
                id="access-token"
                type="password"
                autoComplete="off"
                value={tokenDraft}
                onChange={(e) => setTokenDraft(e.target.value)}
                placeholder="Paste token"
                className="h-10 w-full bg-surface sm:w-72"
              />
              <Button type="submit" disabled={!tokenDraft.trim()} className="h-10 bg-brand text-white shadow-glow">
                Save token
              </Button>
            </form>
          </div>
        </section>
      ) : null}

      {(IS_MOCK || hasToken) && (
        <section className="flex shrink-0 flex-col gap-3 rounded-2xl bg-surface p-3 shadow-card ring-1 ring-line md:flex-row md:flex-wrap md:items-end">
          <div className="flex items-center gap-2 pr-2 text-sm font-semibold text-violet md:self-center">
            <ListFilter className="h-4 w-4" aria-hidden /> Filters
          </div>
          <label className="flex flex-col gap-1 text-xs font-semibold text-muted">
            From
            <Input
              type="date"
              value={start}
              onChange={(e) => {
                setStart(e.target.value);
                setLimit(PAGE_SIZE);
              }}
                            className="h-9 w-40 bg-canvas"
            />
          </label>
          <label className="flex flex-col gap-1 text-xs font-semibold text-muted">
            To
            <Input
              type="date"
              value={end}
              onChange={(e) => {
                setEnd(e.target.value);
                setLimit(PAGE_SIZE);
              }}
                            className="h-9 w-40 bg-canvas"
            />
          </label>
          <label className="flex flex-col gap-1 text-xs font-semibold text-muted">
            Status
            <Select
              value={status}
              onChange={(e) => {
                setStatus(e.target.value as (typeof STATUSES)[number]);
                setLimit(PAGE_SIZE);
              }}
              className="h-9 w-40 bg-canvas"
            >
              {STATUSES.map((s) => (
                <option key={s} value={s}>
                  {s === "ALL" ? "All statuses" : s.charAt(0) + s.slice(1).toLowerCase()}
                </option>
              ))}
            </Select>
          </label>
          <p className="text-xs text-muted md:ml-auto">
            {IS_MOCK
              ? `Synthetic demo data for ${activeUser.merchantId}: ${formatCount(dateRows.length)} of ${formatCount(allDemoRows.length)} transactions in these dates.`
              : "Up to 100 most recent rows are shown. Dates are your local calendar days."}
          </p>
        </section>
      )}

      {!IS_MOCK && hasToken && summaryQuery.isLoading ? <LoadingState label="Loading figures…" /> : null}
      {!IS_MOCK && summaryQuery.error ? <ErrorState message={(summaryQuery.error as Error).message} /> : null}

      {dashboard ? (
        <>
          <section aria-label="Dashboard" className="grid shrink-0 gap-4 sm:grid-cols-2 xl:grid-cols-4">
            <KpiCard
              tone="blue"
              label="Transactions"
              value={formatCount(dashboard.transactionCount)}
              definition={IS_MOCK ? "Demo rows loaded" : "All statuses in the selected dates"}
            />
            <KpiCard
              tone="teal"
              label="Approved volume"
              value={
                dashboard.approvedByCurrency.length === 0
                  ? "—"
                  : dashboard.approvedByCurrency.map((v) => formatMoney(v.amount, v.currency)).join(" · ")
              }
              definition="APPROVED transactions, one figure per currency"
            />
            <KpiCard
              tone="violet"
              label="Decline rate"
              value={formatRate(dashboard.declineRate)}
              definition="DECLINED ÷ (APPROVED + DECLINED)"
            />
            <KpiCard
              tone="rose"
              label="Declined"
              value={formatCount(dashboard.declined)}
              definition="DECLINED transactions in the selected dates"
            />
          </section>

          <section className="grid min-h-[10rem] flex-[1_1_0] gap-3 lg:grid-cols-2">
            <Section icon={PieIcon} title="Transactions by status" tone="bg-violet/10 text-violet" className="flex h-full min-h-0 flex-col">
              <div className="flex min-h-0 flex-1 items-center p-3">
                <StatusDonut data={dashboard.statusCounts} />
              </div>
            </Section>
            <Section icon={BarChart3} title="Transactions by card network" tone="bg-teal/10 text-teal" className="flex h-full min-h-0 flex-col">
              <div className="flex min-h-0 flex-1 items-center p-3">
                <SimpleBar data={dashboard.networkCounts} valueLabel="Transactions" format={formatCount} />
              </div>
            </Section>
          </section>
        </>
      ) : null}

      {(IS_MOCK || hasToken) && (
        <Section
          icon={History}
          title="Recent transactions"
          hint="Scroll inside the table to see more rows"
          tone="bg-accent/10 text-accent"
          className="flex min-h-[11rem] flex-[1_1_0] flex-col"
        >
          {!IS_MOCK && listQuery.isLoading ? <div className="p-4"><LoadingState label="Loading transactions…" /></div> : null}
          {!IS_MOCK && listQuery.error ? (
            <div className="p-4"><ErrorState message={(listQuery.error as Error).message} /></div>
          ) : null}
          <div className="min-h-[6rem] flex-1 overflow-auto">
            <table className="w-full min-w-[720px] text-left text-sm">
              <thead className="sticky top-0 z-10 bg-canvas text-[11px] uppercase tracking-wider text-muted shadow-[inset_0_-1px_0_theme(colors.line)]">
                <tr>
                  <th className="px-5 py-3 font-semibold">Time</th>
                  <th className="px-4 py-3 font-semibold">Transaction</th>
                  <th className="px-4 py-3 font-semibold">Card</th>
                  <th className="px-4 py-3 font-semibold">Region</th>
                  <th className="px-4 py-3 text-right font-semibold">Amount</th>
                  <th className="px-4 py-3 font-semibold">Status</th>
                  <th className="px-5 py-3 font-semibold">Decline reason</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-line/70">
                {rows.map((t) => (
                  <tr key={t.id} className="transition hover:bg-accent/5">
                    <td className="whitespace-nowrap px-5 py-3 text-muted">{shortTime(t.at)}</td>
                    <td className="px-4 py-3 font-mono text-xs text-ink">{t.id}</td>
                    <td className="px-4 py-3">
                      <span className="font-medium text-ink">{t.network}</span>{" "}
                      <span className="rounded-full bg-canvas px-2 py-0.5 text-[11px] text-muted ring-1 ring-line">
                        {t.cardType.toLowerCase()}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-muted">{t.region}</td>
                    <td className="whitespace-nowrap px-4 py-3 text-right font-semibold tabular-nums text-ink">
                      {formatMoney(t.amount, t.currency)}
                    </td>
                    <td className="px-4 py-3">
                      <span
                        className={cn(
                          "inline-flex rounded-full px-2.5 py-0.5 text-xs font-semibold ring-1",
                          STATUS_PILL[t.status] ?? "bg-canvas text-muted ring-line",
                        )}
                      >
                        {t.status.charAt(0) + t.status.slice(1).toLowerCase()}
                      </span>
                    </td>
                    <td className="px-5 py-3 text-muted">{t.declineReason ?? "—"}</td>
                  </tr>
                ))}
                {rows.length === 0 && (IS_MOCK || !listQuery.isLoading) && !listQuery.error ? (
                  <tr>
                    <td colSpan={7} className="px-5 py-10 text-center text-muted">
                      No transactions match these filters.
                    </td>
                  </tr>
                ) : null}
              </tbody>
            </table>
          </div>
          <div className="flex shrink-0 flex-wrap items-center justify-between gap-3 border-t border-line bg-canvas/60 px-5 py-2.5 text-xs text-muted">
            <span>
              Showing <span className="font-semibold text-ink">{formatCount(rows.length)}</span> of{" "}
              <span className="font-semibold text-ink">{formatCount(matching)}</span>
            </span>
            {canLoadMore ? (
              <button
                type="button"
                onClick={() => setLimit((l) => (IS_MOCK ? l + PAGE_SIZE : Math.min(l + PAGE_SIZE, MAX_ROWS)))}
                className="rounded-full bg-brand px-4 py-1.5 font-semibold text-white shadow-glow transition hover:opacity-95"
              >
                Show more
              </button>
            ) : null}
          </div>
        </Section>
      )}


      <ChatWidget
        blockedReason={needsToken ? "Enter this user's access token above before asking questions." : null}
      />
    </div>
  );
}
