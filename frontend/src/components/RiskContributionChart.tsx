"use client";

import {
  ResponsiveContainer,
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  Cell,
} from "recharts";
import { TICKER_COLORS, tickerLabel, type RiskContribution } from "@/lib/api";

interface RiskContributionChartProps {
  data: RiskContribution | undefined;
}

export default function RiskContributionChart({
  data,
}: RiskContributionChartProps) {
  if (!data) {
    return (
      <div className="w-full h-full flex items-center justify-center">
        <span className="text-text-muted font-mono text-sm animate-pulse">
          Risk Contribution — loading...
        </span>
      </div>
    );
  }

  const chartData = Object.entries(data.contributions)
    .map(([ticker, value]) => ({
      ticker,
      label: tickerLabel(ticker),
      value: +(value * 100).toFixed(1),
      color: TICKER_COLORS[ticker] || "#8a9ab2",
    }))
    .sort((a, b) => b.value - a.value);

  return (
    <div className="flex flex-col h-full p-2">
      <div className="text-[10px] font-mono text-text-muted uppercase tracking-[0.15em] mb-2 px-1">
        Risk Contribution
      </div>
      <div className="flex-1">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={chartData}
            layout="vertical"
            margin={{ top: 0, right: 24, bottom: 0, left: 0 }}
          >
            <XAxis
              type="number"
              tick={{ fontSize: 10, fill: "#5a6a82" }}
              tickFormatter={(v) => `${v}%`}
              domain={[0, "auto"]}
            />
            <YAxis
              type="category"
              dataKey="label"
              tick={{ fontSize: 11, fill: "#8a9ab2", fontFamily: "JetBrains Mono" }}
              width={70}
            />
            <Tooltip
              contentStyle={{
                background: "#0d1117",
                border: "1px solid #1e2d45",
                borderRadius: 8,
                fontSize: 12,
                fontFamily: "JetBrains Mono",
              }}
              formatter={(value) => [`${Number(value).toFixed(1)}%`, "Contribution"]}
            />
            <Bar dataKey="value" radius={[0, 4, 4, 0]} barSize={24}>
              {chartData.map((entry) => (
                <Cell key={entry.ticker} fill={entry.color} fillOpacity={0.75} />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  );
}
