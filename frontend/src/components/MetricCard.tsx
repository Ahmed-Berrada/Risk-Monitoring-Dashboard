"use client";

import { type MetricValue } from "@/lib/api";

interface MetricCardProps {
  label: string;
  value: number | null;
  format?: "pct" | "ratio" | "number";
  subtitle?: string;
  status?: "green" | "amber" | "red" | "neutral";
}

function formatValue(
  value: number | null,
  format: "pct" | "ratio" | "number" = "pct"
): string {
  if (value === null || value === undefined) return "—";
  switch (format) {
    case "pct":
      return `${(value * 100).toFixed(2)}%`;
    case "ratio":
      return value.toFixed(2);
    case "number":
      return value.toFixed(4);
  }
}

const STATUS_COLORS = {
  green: "bg-green-500/20 text-green-400",
  amber: "bg-yellow-500/20 text-yellow-400",
  red: "bg-red-500/20 text-red-400",
  neutral: "bg-accent-dim text-accent",
};

export default function MetricCard({
  label,
  value,
  format = "pct",
  subtitle,
  status = "neutral",
}: MetricCardProps) {
  return (
    <div className="rounded-lg bg-bg-2 border border-border gold-border p-4 flex flex-col gap-1.5 min-h-[100px]">
      <span className="text-text-muted text-[10px] font-mono uppercase tracking-[0.15em]">
        {label}
      </span>
      <span className="text-2xl font-display text-accent leading-tight">
        {formatValue(value, format)}
      </span>
      {subtitle && (
        <span
          className={`text-[10px] font-mono px-1.5 py-0.5 rounded w-fit ${STATUS_COLORS[status]}`}
        >
          {subtitle}
        </span>
      )}
    </div>
  );
}

/** Extract a specific metric from the summary for a ticker */
export function getMetric(
  metrics: MetricValue[] | undefined,
  ticker: string,
  metricName: string
): number | null {
  if (!metrics) return null;
  const m = metrics.find(
    (m) => m.ticker === ticker && m.metric_name === metricName
  );
  return m?.value ?? null;
}
