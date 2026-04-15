"use client";

import { useState } from "react";
import {
  BarChart,
  Bar,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  Cell,
} from "recharts";
import {
  type AllScenariosResponse,
  type StressResult,
  TICKER_LABELS,
  TICKER_COLORS,
} from "@/lib/api";

interface Props {
  data: AllScenariosResponse | undefined;
}

const SEVERITY_COLORS: Record<string, string> = {
  extreme: "#ef4444",
  severe: "#f97316",
  custom: "#c8a84b",
};

export default function StressTestPanel({ data }: Props) {
  const [selected, setSelected] = useState<string | null>(null);

  if (!data) {
    return (
      <div className="h-full flex items-center justify-center text-text-muted text-xs font-mono">
        Loading stress tests…
      </div>
    );
  }

  const scenarioIds = data.available;
  const scenarios = data.scenarios;

  // Prepare comparison chart data
  const chartData = scenarioIds.map((id) => {
    const s = scenarios[id];
    return {
      name: s?.scenario.name.replace(/^\d{4}\s*/, "").slice(0, 12) || id,
      loss: s ? Math.abs(s.portfolio_impact.total_loss * 100) : 0,
      severity: s?.scenario.severity || "unknown",
      id,
    };
  });

  const selectedResult = selected ? scenarios[selected] : null;

  return (
    <div className="h-full flex flex-col px-3 pt-2 pb-2 overflow-hidden">
      {/* Header */}
      <div className="flex items-center justify-between mb-2">
        <span className="text-[10px] font-mono text-text-muted uppercase tracking-[0.15em]">
          Stress Testing
        </span>
        <span className="text-[9px] font-mono text-text-dim">
          {scenarioIds.length} scenarios
        </span>
      </div>

      {/* Comparison bar chart */}
      <div className="h-[120px] mb-2">
        <ResponsiveContainer width="100%" height="100%">
          <BarChart
            data={chartData}
            layout="vertical"
            margin={{ top: 0, right: 4, bottom: 0, left: 4 }}
            onClick={(state: Record<string, unknown>) => {
              const payload = state?.activePayload as
                | Array<{ payload: { id: string } }>
                | undefined;
              if (payload?.[0]) {
                const id = payload[0].payload.id;
                setSelected(selected === id ? null : id);
              }
            }}
          >
            <XAxis
              type="number"
              tick={{ fontSize: 8, fill: "#8a8f98" }}
              axisLine={false}
              tickLine={false}
              tickFormatter={(v) => `${v}%`}
            />
            <YAxis
              type="category"
              dataKey="name"
              tick={{ fontSize: 8, fill: "#8a8f98" }}
              axisLine={false}
              tickLine={false}
              width={80}
            />
            <Tooltip
              contentStyle={{
                background: "#0d1117",
                border: "1px solid #1e2530",
                borderRadius: 6,
                fontSize: 10,
              }}
              formatter={(value) => [
                `${Number(value).toFixed(1)}%`,
                "Loss",
              ]}
            />
            <Bar dataKey="loss" radius={[0, 3, 3, 0]} cursor="pointer">
              {chartData.map((entry, i) => (
                <Cell
                  key={i}
                  fill={
                    selected === entry.id
                      ? "#c8a84b"
                      : SEVERITY_COLORS[entry.severity] || "#6b7280"
                  }
                  opacity={selected && selected !== entry.id ? 0.3 : 0.8}
                />
              ))}
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>

      {/* Selected scenario detail */}
      {selectedResult ? (
        <ScenarioDetail result={selectedResult} />
      ) : (
        <div className="flex-1 flex items-center justify-center text-text-muted text-[9px] font-mono">
          Click a scenario for details
        </div>
      )}
    </div>
  );
}

function ScenarioDetail({ result }: { result: StressResult }) {
  const pi = result.portfolio_impact;
  const isHistorical = result.data_source === "historical";

  return (
    <div className="flex-1 overflow-y-auto space-y-2">
      {/* Scenario info */}
      <div className="flex items-center justify-between">
        <span className="text-[10px] font-mono text-accent">
          {result.scenario.name}
        </span>
        <span
          className={`text-[8px] font-mono px-1.5 py-0.5 rounded ${
            isHistorical
              ? "bg-green-500/15 text-green-400"
              : "bg-yellow-500/15 text-yellow-400"
          }`}
        >
          {result.data_source}
        </span>
      </div>

      <p className="text-[8px] font-mono text-text-muted">
        {result.scenario.description}
      </p>

      {/* Impact stats */}
      <div className="grid grid-cols-3 gap-1.5">
        <StatBox
          label="Total Loss"
          value={`${(pi.total_loss * 100).toFixed(1)}%`}
          negative
        />
        <StatBox
          label="Max DD"
          value={`${(pi.max_drawdown * 100).toFixed(1)}%`}
          negative
        />
        <StatBox
          label="Worst Day"
          value={`${(pi.worst_day * 100).toFixed(2)}%`}
          negative
        />
      </div>

      {isHistorical && (
        <div className="text-[8px] font-mono text-text-muted text-center">
          {pi.negative_days}/{pi.total_days} negative days over{" "}
          {result.duration_days} trading days
        </div>
      )}

      {/* Per-asset breakdown */}
      <div className="space-y-1">
        {Object.entries(result.per_asset).map(([ticker, impact]) => (
          <div
            key={ticker}
            className="flex items-center justify-between rounded px-2 py-1 bg-bg/50 border border-border/20"
          >
            <div className="flex items-center gap-1.5">
              <div
                className="w-1.5 h-1.5 rounded-full"
                style={{ backgroundColor: TICKER_COLORS[ticker] || "#888" }}
              />
              <span className="text-[9px] font-mono text-text-dim">
                {TICKER_LABELS[ticker] || ticker}
              </span>
            </div>
            <div className="flex items-center gap-3">
              <span className="text-[9px] font-mono text-red-400">
                {(impact.total_return * 100).toFixed(1)}%
              </span>
              {impact.contribution_to_loss !== undefined && (
                <span className="text-[8px] font-mono text-text-muted">
                  contrib:{" "}
                  {(impact.contribution_to_loss * 100).toFixed(1)}%
                </span>
              )}
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

function StatBox({
  label,
  value,
  negative,
}: {
  label: string;
  value: string;
  negative?: boolean;
}) {
  return (
    <div className="rounded bg-bg/50 border border-border/20 px-2 py-1.5 text-center">
      <div className="text-[7px] font-mono text-text-muted uppercase tracking-wider">
        {label}
      </div>
      <div
        className={`text-[11px] font-mono ${
          negative ? "text-red-400" : "text-text-dim"
        }`}
      >
        {value}
      </div>
    </div>
  );
}
