"use client";

import { type MetricValue, tickerLabel, TICKER_COLORS } from "@/lib/api";
import { getMetric } from "./MetricCard";

interface AssetTableProps {
  metrics: MetricValue[] | undefined;
}

const METRIC_CONFIG = [
  { key: "var_95", label: "VaR 95%", format: "pct" as const },
  { key: "var_99", label: "VaR 99%", format: "pct" as const },
  { key: "cvar_95", label: "CVaR 95%", format: "pct" as const },
  { key: "volatility_21d", label: "Vol 21d", format: "pct" as const },
  { key: "volatility_63d", label: "Vol 63d", format: "pct" as const },
  { key: "max_drawdown", label: "Max DD", format: "pct" as const },
  { key: "current_drawdown", label: "Curr DD", format: "pct" as const },
  { key: "sharpe_ratio", label: "Sharpe", format: "ratio" as const },
  { key: "sortino_ratio", label: "Sortino", format: "ratio" as const },
  { key: "beta", label: "Beta", format: "ratio" as const },
];

const TICKERS = ["PORTFOLIO", "^GSPC", "GLE.PA", "SIE.DE"];

function fmt(value: number | null, format: "pct" | "ratio"): string {
  if (value === null) return "—";
  return format === "pct" ? `${(value * 100).toFixed(2)}%` : value.toFixed(2);
}

function riskColor(metricKey: string, value: number | null): string {
  if (value === null) return "text-text-muted";
  // Higher = worse for VaR, CVaR, volatility, drawdown
  if (["var_95", "var_99", "cvar_95", "cvar_99", "volatility_21d", "volatility_63d", "max_drawdown", "current_drawdown"].includes(metricKey)) {
    if (value > 0.05) return "text-red-400";
    if (value > 0.03) return "text-yellow-400";
    return "text-green-400";
  }
  // Higher = better for Sharpe, Sortino
  if (["sharpe_ratio", "sortino_ratio"].includes(metricKey)) {
    if (value > 1) return "text-green-400";
    if (value > 0.5) return "text-yellow-400";
    return "text-red-400";
  }
  return "text-text-dim";
}

export default function AssetTable({ metrics }: AssetTableProps) {
  if (!metrics) {
    return (
      <div className="w-full h-full flex items-center justify-center">
        <span className="text-text-muted font-mono text-sm animate-pulse">
          Loading metrics...
        </span>
      </div>
    );
  }

  return (
    <div className="overflow-x-auto">
      <table className="w-full text-xs font-mono">
        <thead>
          <tr className="border-b border-border">
            <th className="text-left text-text-muted text-[10px] uppercase tracking-wider py-2 px-2 sticky left-0 bg-bg-2">
              Metric
            </th>
            {TICKERS.map((ticker) => (
              <th
                key={ticker}
                className="text-right text-[10px] uppercase tracking-wider py-2 px-2"
                style={{ color: TICKER_COLORS[ticker] || "#8a9ab2" }}
              >
                {tickerLabel(ticker)}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {METRIC_CONFIG.map(({ key, label, format }) => (
            <tr
              key={key}
              className="border-b border-border/50 hover:bg-bg-3/50 transition-colors"
            >
              <td className="py-1.5 px-2 text-text-dim sticky left-0 bg-bg-2">
                {label}
              </td>
              {TICKERS.map((ticker) => {
                const val = getMetric(metrics, ticker, key);
                return (
                  <td
                    key={ticker}
                    className={`py-1.5 px-2 text-right ${riskColor(key, val)}`}
                  >
                    {fmt(val, format)}
                  </td>
                );
              })}
            </tr>
          ))}
        </tbody>
      </table>
    </div>
  );
}
