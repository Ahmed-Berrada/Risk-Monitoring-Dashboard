"use client";

import {
  ResponsiveContainer,
  AreaChart,
  Area,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  CartesianGrid,
} from "recharts";
import { TICKER_COLORS, tickerLabel, type RollingSeries, type AssetSeries } from "@/lib/api";

interface DrawdownChartProps {
  series: RollingSeries | undefined;
}

export default function DrawdownChart({ series }: DrawdownChartProps) {
  if (!series) {
    return (
      <div className="w-full h-full flex items-center justify-center">
        <span className="text-text-muted font-mono text-sm animate-pulse">
          Drawdown — loading...
        </span>
      </div>
    );
  }

  const tickers = Object.keys(series).filter(
    (k) => k !== "correlations" && k !== "PORTFOLIO"
  );
  const allTickers = [...tickers, "PORTFOLIO"];

  const portfolioSeries = series["PORTFOLIO"] as AssetSeries | undefined;
  if (!portfolioSeries) return null;

  const dates = portfolioSeries.drawdown.dates;
  const data = dates.map((date, i) => {
    const point: Record<string, string | number> = { date };
    for (const ticker of allTickers) {
      const ts = (series[ticker] as AssetSeries)?.drawdown;
      if (ts) {
        point[ticker] = +(ts.values[i] * 100).toFixed(2); // Already negative
      }
    }
    return point;
  });

  const step = Math.max(1, Math.floor(data.length / 300));
  const sampled = data.filter((_, i) => i % step === 0 || i === data.length - 1);

  return (
    <ResponsiveContainer width="100%" height="100%">
      <AreaChart data={sampled} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#1e2d45" />
        <XAxis
          dataKey="date"
          tick={{ fontSize: 10, fill: "#5a6a82" }}
          tickFormatter={(d) => d.slice(5)}
          interval={Math.floor(sampled.length / 6)}
        />
        <YAxis
          tick={{ fontSize: 10, fill: "#5a6a82" }}
          tickFormatter={(v) => `${v}%`}
          width={48}
        />
        <Tooltip
          contentStyle={{
            background: "#0d1117",
            border: "1px solid #1e2d45",
            borderRadius: 8,
            fontSize: 12,
            fontFamily: "JetBrains Mono",
          }}
          labelStyle={{ color: "#8a9ab2" }}
          formatter={(value) => [`${Number(value).toFixed(2)}%`, ""]}
        />
        <Legend
          wrapperStyle={{ fontSize: 11, fontFamily: "JetBrains Mono" }}
          formatter={(value) => tickerLabel(value)}
        />
        {allTickers.map((ticker) => (
          <Area
            key={ticker}
            type="monotone"
            dataKey={ticker}
            stroke={TICKER_COLORS[ticker] || "#8a9ab2"}
            fill={TICKER_COLORS[ticker] || "#8a9ab2"}
            fillOpacity={ticker === "PORTFOLIO" ? 0.15 : 0.05}
            strokeWidth={ticker === "PORTFOLIO" ? 2 : 1.2}
            dot={false}
            name={ticker}
          />
        ))}
      </AreaChart>
    </ResponsiveContainer>
  );
}
