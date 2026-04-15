"use client";

import {
  ResponsiveContainer,
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  Legend,
  CartesianGrid,
} from "recharts";
import { TICKER_COLORS, tickerLabel, type RollingSeries, type AssetSeries } from "@/lib/api";

interface VolatilityChartProps {
  series: RollingSeries | undefined;
  window?: "volatility_21d" | "volatility_63d";
}

export default function VolatilityChart({
  series,
  window = "volatility_21d",
}: VolatilityChartProps) {
  if (!series) {
    return <ChartPlaceholder label="Rolling Volatility" />;
  }

  // Build merged data: [{date, "^GSPC": 0.15, "GLE.PA": 0.25, ...}]
  const tickers = Object.keys(series).filter(
    (k) => k !== "correlations" && k !== "PORTFOLIO"
  );
  const allTickers = [...tickers, "PORTFOLIO"];

  // Use PORTFOLIO dates as reference (they all align)
  const portfolioSeries = series["PORTFOLIO"] as AssetSeries | undefined;
  if (!portfolioSeries) return <ChartPlaceholder label="Rolling Volatility" />;

  const dates = portfolioSeries[window].dates;
  const data = dates.map((date, i) => {
    const point: Record<string, string | number> = { date };
    for (const ticker of allTickers) {
      const ts = (series[ticker] as AssetSeries)?.[window];
      if (ts) {
        point[ticker] = +(ts.values[i] * 100).toFixed(2); // Convert to %
      }
    }
    return point;
  });

  // Downsample for performance: show every nth point
  const step = Math.max(1, Math.floor(data.length / 300));
  const sampled = data.filter((_, i) => i % step === 0 || i === data.length - 1);

  return (
    <ResponsiveContainer width="100%" height="100%">
      <LineChart data={sampled} margin={{ top: 8, right: 16, bottom: 0, left: 0 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#1e2d45" />
        <XAxis
          dataKey="date"
          tick={{ fontSize: 10, fill: "#5a6a82" }}
          tickFormatter={(d) => d.slice(5)} // "MM-DD"
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
          labelFormatter={(label) => label}
        />
        <Legend
          wrapperStyle={{ fontSize: 11, fontFamily: "JetBrains Mono" }}
          formatter={(value) => tickerLabel(value)}
        />
        {allTickers.map((ticker) => (
          <Line
            key={ticker}
            type="monotone"
            dataKey={ticker}
            stroke={TICKER_COLORS[ticker] || "#8a9ab2"}
            strokeWidth={ticker === "PORTFOLIO" ? 2.5 : 1.5}
            dot={false}
            name={ticker}
          />
        ))}
      </LineChart>
    </ResponsiveContainer>
  );
}

function ChartPlaceholder({ label }: { label: string }) {
  return (
    <div className="w-full h-full flex items-center justify-center">
      <span className="text-text-muted font-mono text-sm animate-pulse">
        {label} — loading...
      </span>
    </div>
  );
}
