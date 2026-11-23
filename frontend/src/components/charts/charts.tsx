"use client";

import { ArrowDownRight, ArrowUpRight, Minus } from "lucide-react";
import {
  Bar,
  BarChart,
  CartesianGrid,
  Cell,
  Legend,
  Pie,
  PieChart,
  ResponsiveContainer,
  Tooltip,
  XAxis,
  YAxis,
} from "recharts";
import { Card, CardContent } from "@/components/ui/primitives";

const PALETTE = ["#2563eb", "#7c3aed", "#0d9488", "#f59e0b", "#e11d48"];

export type KpiTone = "blue" | "violet" | "teal" | "amber" | "rose";

const TONE_CLASS: Record<KpiTone, { bar: string; dot: string }> = {
  blue: { bar: "from-accent to-sky-400", dot: "bg-accent" },
  violet: { bar: "from-violet to-fuchsia-500", dot: "bg-violet" },
  teal: { bar: "from-teal to-emerald-400", dot: "bg-teal" },
  amber: { bar: "from-amber to-yellow-400", dot: "bg-amber" },
  rose: { bar: "from-rose to-pink-500", dot: "bg-rose" },
};

export interface KpiCardProps {
  label: string;
  value: string;
  definition: string;
  tone?: KpiTone;
  /** Previous-period value, when the backend provides one. Otherwise omitted. */
  previous?: string | null;
  changePct?: number | null;
}

export function KpiCard({ label, value, definition, tone = "blue", previous, changePct }: KpiCardProps) {
  const hasComparison = previous !== undefined && previous !== null && changePct !== undefined && changePct !== null;
  const Trend = !hasComparison || changePct === 0 ? Minus : changePct > 0 ? ArrowUpRight : ArrowDownRight;
  const t = TONE_CLASS[tone];
  return (
    <Card className="relative overflow-hidden shadow-lift">
      <div className={`absolute inset-x-0 top-0 h-1 bg-gradient-to-r ${t.bar}`} aria-hidden />
      <CardContent className="space-y-1 p-3.5">
        <p className="flex items-center gap-2 text-xs font-semibold uppercase tracking-wide text-muted" title={definition}>
          <span className={`inline-block h-2 w-2 rounded-full ${t.dot}`} aria-hidden />
          {label} <span className="sr-only">{definition}</span>
        </p>
        <p className="text-xl font-bold tracking-tight text-ink">{value}</p>
        {hasComparison ? (
          <p className="flex items-center gap-1 text-xs text-muted">
            <Trend className="h-3.5 w-3.5" aria-hidden />
            {`${changePct > 0 ? "+" : ""}${(changePct * 100).toFixed(1)}% vs ${previous}`}
          </p>
        ) : (
          <p className="text-xs text-muted">No comparison available.</p>
        )}
      </CardContent>
    </Card>
  );
}

export interface DonutDatum {
  name: string;
  value: number;
}

export function StatusDonut({ data }: { data: DonutDatum[] }) {
  const total = data.reduce((sum, d) => sum + d.value, 0);
  return (
    <div className="flex flex-col items-center gap-4 md:flex-row">
      <div className="h-32 w-32 shrink-0">
        <ResponsiveContainer width="100%" height="100%">
          <PieChart>
            <Pie data={data} dataKey="value" nameKey="name" innerRadius={34} outerRadius={56} paddingAngle={2}>
              {data.map((_, i) => (
                <Cell key={i} fill={PALETTE[i % PALETTE.length]} />
              ))}
            </Pie>
            <Tooltip formatter={(v: number) => `${v.toLocaleString()} (${((v / total) * 100).toFixed(1)}%)`} />
          </PieChart>
        </ResponsiveContainer>
      </div>
      <ul className="w-full space-y-2 text-sm">
        {data.map((d, i) => (
          <li key={d.name} className="flex items-center justify-between gap-4">
            <span className="flex items-center gap-2 text-ink">
              <span className="inline-block h-2.5 w-2.5 rounded-full" style={{ background: PALETTE[i % PALETTE.length] }} />
              {d.name}
            </span>
            <span className="text-muted">
              {d.value.toLocaleString()} · {total ? ((d.value / total) * 100).toFixed(1) : "0.0"}%
            </span>
          </li>
        ))}
      </ul>
    </div>
  );
}

export interface BarDatum {
  label: string;
  value: number;
}

/** One unit per chart. Callers must pass a single currency or a unitless rate, never a mix. */
export function SimpleBar({
  data,
  valueLabel,
  format,
}: {
  data: BarDatum[];
  valueLabel: string;
  format: (n: number) => string;
}) {
  return (
    <div className="h-full w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 8, left: 8, bottom: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
          <XAxis dataKey="label" tick={{ fontSize: 12, fill: "#64748b" }} />
          <YAxis tickFormatter={format} tick={{ fontSize: 12, fill: "#64748b" }} width={80} />
          <Tooltip formatter={(v: number) => [format(v), valueLabel]} />
          <Bar dataKey="value" fill="#7c3aed" radius={[6, 6, 0, 0]} />
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}

export interface GroupedDatum {
  label: string;
  [series: string]: string | number;
}

/** Grouped comparison, e.g. credit vs debit decline rates. Series share one unit. */
export function GroupedBar({
  data,
  series,
  format,
}: {
  data: GroupedDatum[];
  series: { key: string; label: string }[];
  format: (n: number) => string;
}) {
  return (
    <div className="h-64 w-full">
      <ResponsiveContainer width="100%" height="100%">
        <BarChart data={data} margin={{ top: 8, right: 8, left: 8, bottom: 8 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e2e8f0" vertical={false} />
          <XAxis dataKey="label" tick={{ fontSize: 12, fill: "#64748b" }} />
          <YAxis tickFormatter={format} tick={{ fontSize: 12, fill: "#64748b" }} width={80} />
          <Tooltip formatter={(v: number) => format(v)} />
          <Legend />
          {series.map((s, i) => (
            <Bar key={s.key} dataKey={s.key} name={s.label} fill={PALETTE[i % PALETTE.length]} radius={[4, 4, 0, 0]} />
          ))}
        </BarChart>
      </ResponsiveContainer>
    </div>
  );
}
