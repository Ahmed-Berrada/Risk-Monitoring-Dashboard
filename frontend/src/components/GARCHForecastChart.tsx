"use client";

import {
  LineChart,
  Line,
  XAxis,
  YAxis,
  Tooltip,
  ResponsiveContainer,
  ReferenceLine,
} from "recharts";
import {
  type GARCHResponse,
  TICKER_LABELS,
  TICKER_COLORS,
} from "@/lib/api";

interface Props {
  data: GARCHResponse | undefined;
}

export default function GARCHForecastChart({ data }: Props) {
  if (!data) {
    return (
      <div className="h-full flex items-center justify-center text-text-muted text-xs font-mono">
        Loading GARCH…
      </div>
    );
  }

  const tickers = Object.keys(data.forecasts).filter(
    (t) => data.forecasts[t] !== null
  );

  return (
    <div className="h-full flex flex-col px-3 pt-2 pb-1">
      <div className="flex items-center justify-between mb-1">
        <span className="text-[10px] font-mono text-text-muted uppercase tracking-[0.15em]">
          GARCH Volatility Forecast
        </span>
        <span className="text-[9px] font-mono text-text-dim">
          10-day horizon
        </span>
      </div>

      {/* Forecast bars per ticker */}
      <div className="flex-1 flex flex-col gap-2 overflow-y-auto pr-1">
        {tickers.map((ticker) => {
          const result = data.forecasts[ticker]!;
          const { forecast } = result;
          const { current_vol, forecast_vol, params } = forecast;

          // Prepare chart data: current + forecast days
          const chartData = [
            { day: "Now", vol: current_vol * 100 },
            ...forecast_vol.map((v, i) => ({
              day: `D+${i + 1}`,
              vol: v * 100,
            })),
          ];

          const trending =
            forecast_vol[forecast_vol.length - 1] > current_vol
              ? "rising"
              : forecast_vol[forecast_vol.length - 1] < current_vol * 0.98
              ? "falling"
              : "stable";

          return (
            <div key={ticker} className="flex-1 min-h-[80px]">
              <div className="flex items-center justify-between mb-0.5">
                <div className="flex items-center gap-2">
                  <div
                    className="w-1.5 h-1.5 rounded-full"
                    style={{ backgroundColor: TICKER_COLORS[ticker] }}
                  />
                  <span className="text-[10px] font-mono text-text-dim">
                    {TICKER_LABELS[ticker] || ticker}
                  </span>
                </div>
                <div className="flex items-center gap-3">
                  <span className="text-[9px] font-mono text-text-muted">
                    α={params.alpha.toFixed(3)} β={params.beta.toFixed(3)}
                  </span>
                  <span
                    className={`text-[9px] font-mono px-1.5 py-0.5 rounded ${
                      trending === "rising"
                        ? "bg-red-500/15 text-red-400"
                        : trending === "falling"
                        ? "bg-green-500/15 text-green-400"
                        : "bg-accent/15 text-accent"
                    }`}
                  >
                    {trending === "rising"
                      ? "↑ Rising"
                      : trending === "falling"
                      ? "↓ Falling"
                      : "→ Stable"}
                  </span>
                </div>
              </div>
              <ResponsiveContainer width="100%" height={70}>
                <LineChart data={chartData} margin={{ top: 2, right: 4, bottom: 0, left: 4 }}>
                  <XAxis
                    dataKey="day"
                    tick={{ fontSize: 8, fill: "#8a8f98" }}
                    axisLine={false}
                    tickLine={false}
                  />
                  <YAxis
                    domain={["auto", "auto"]}
                    tick={{ fontSize: 8, fill: "#8a8f98" }}
                    axisLine={false}
                    tickLine={false}
                    width={30}
                    tickFormatter={(v) => `${v.toFixed(1)}%`}
                  />
                  <Tooltip
                    contentStyle={{
                      background: "#0d1117",
                      border: "1px solid #1e2530",
                      borderRadius: 6,
                      fontSize: 10,
                    }}
                    formatter={(value) => [
                      `${Number(value).toFixed(2)}%`,
                      "Vol",
                    ]}
                  />
                  <ReferenceLine
                    y={current_vol * 100}
                    stroke="#c8a84b"
                    strokeDasharray="3 3"
                    strokeOpacity={0.4}
                  />
                  <Line
                    type="monotone"
                    dataKey="vol"
                    stroke={TICKER_COLORS[ticker]}
                    strokeWidth={1.5}
                    dot={{ r: 2, fill: TICKER_COLORS[ticker] }}
                    activeDot={{ r: 3 }}
                  />
                </LineChart>
              </ResponsiveContainer>
            </div>
          );
        })}
      </div>

      {/* Persistence summary */}
      <div className="flex items-center justify-center gap-4 mt-1 pt-1 border-t border-border/30">
        {tickers.map((ticker) => {
          const p = data.forecasts[ticker]?.forecast.params.persistence ?? 0;
          return (
            <span key={ticker} className="text-[8px] font-mono text-text-muted">
              {TICKER_LABELS[ticker]}: pers={p.toFixed(3)}
            </span>
          );
        })}
      </div>
    </div>
  );
}
