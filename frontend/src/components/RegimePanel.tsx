"use client";

import { type RegimeResponse, TICKER_LABELS, TICKER_COLORS } from "@/lib/api";

interface Props {
  data: RegimeResponse | undefined;
}

const REGIME_COLORS: Record<string, string> = {
  low_vol: "#22c55e",     // green
  medium_vol: "#eab308",  // yellow
  high_vol: "#ef4444",    // red
};

const REGIME_BG: Record<string, string> = {
  low_vol: "bg-green-500/15",
  medium_vol: "bg-yellow-500/15",
  high_vol: "bg-red-500/15",
};

const REGIME_TEXT: Record<string, string> = {
  low_vol: "text-green-400",
  medium_vol: "text-yellow-400",
  high_vol: "text-red-400",
};

export default function RegimePanel({ data }: Props) {
  if (!data) {
    return (
      <div className="h-full flex items-center justify-center text-text-muted text-xs font-mono">
        Loading regimes…
      </div>
    );
  }

  const { summary, per_asset } = data;
  const overallRegime = summary.overall_regime;
  const tickers = Object.keys(per_asset).filter((t) => per_asset[t] !== null);

  return (
    <div className="h-full flex flex-col px-3 pt-2 pb-2">
      {/* Header */}
      <div className="flex items-center justify-between mb-2">
        <span className="text-[10px] font-mono text-text-muted uppercase tracking-[0.15em]">
          Market Regime
        </span>
        <span className="text-[9px] font-mono text-text-dim">HMM 3-state</span>
      </div>

      {/* Overall regime badge */}
      <div className="flex items-center justify-center mb-3">
        <div
          className={`px-4 py-2 rounded-lg ${REGIME_BG[overallRegime] || "bg-accent/15"} flex flex-col items-center`}
        >
          <span className="text-[9px] font-mono text-text-muted uppercase tracking-wider mb-0.5">
            Overall
          </span>
          <span
            className={`text-lg font-display tracking-wider ${REGIME_TEXT[overallRegime] || "text-accent"}`}
          >
            {summary.overall_display}
          </span>
        </div>
      </div>

      {/* Per-asset regime breakdown */}
      <div className="flex-1 space-y-2 overflow-y-auto">
        {tickers.map((ticker) => {
          const assetData = per_asset[ticker]!;
          const regime = assetData.current_regime;
          const stats = assetData.regime_stats;

          return (
            <div
              key={ticker}
              className="rounded-md bg-bg/50 border border-border/30 p-2"
            >
              {/* Asset header */}
              <div className="flex items-center justify-between mb-1.5">
                <div className="flex items-center gap-1.5">
                  <div
                    className="w-1.5 h-1.5 rounded-full"
                    style={{ backgroundColor: TICKER_COLORS[ticker] }}
                  />
                  <span className="text-[10px] font-mono text-text-dim">
                    {TICKER_LABELS[ticker] || ticker}
                  </span>
                </div>
                <span
                  className={`text-[9px] font-mono px-1.5 py-0.5 rounded ${
                    REGIME_BG[regime] || "bg-accent/15"
                  } ${REGIME_TEXT[regime] || "text-accent"}`}
                >
                  {assetData.current_regime_display}
                </span>
              </div>

              {/* Regime bar (proportional to frequency) */}
              <div className="flex h-2 rounded-full overflow-hidden gap-[1px]">
                {stats.map((s) => (
                  <div
                    key={s.regime}
                    className="h-full rounded-sm transition-all"
                    style={{
                      width: `${s.frequency * 100}%`,
                      backgroundColor: REGIME_COLORS[s.regime] || "#c8a84b",
                      opacity: s.regime === regime ? 1 : 0.3,
                    }}
                    title={`${s.display}: ${(s.frequency * 100).toFixed(1)}% of time`}
                  />
                ))}
              </div>

              {/* Stats row */}
              <div className="flex items-center justify-between mt-1.5">
                {stats.map((s) => (
                  <div key={s.regime} className="flex flex-col items-center">
                    <span className="text-[7px] font-mono text-text-muted uppercase">
                      {s.display}
                    </span>
                    <span className="text-[9px] font-mono text-text-dim">
                      σ {(s.volatility * 100).toFixed(1)}%
                    </span>
                    <span className="text-[8px] font-mono text-text-muted">
                      {(s.frequency * 100).toFixed(0)}%
                    </span>
                  </div>
                ))}
              </div>
            </div>
          );
        })}
      </div>

      {/* Legend */}
      <div className="flex items-center justify-center gap-3 mt-2 pt-1.5 border-t border-border/30">
        {Object.entries(REGIME_COLORS).map(([key, color]) => (
          <div key={key} className="flex items-center gap-1">
            <div
              className="w-1.5 h-1.5 rounded-full"
              style={{ backgroundColor: color }}
            />
            <span className="text-[8px] font-mono text-text-muted capitalize">
              {key.replace("_", " ")}
            </span>
          </div>
        ))}
      </div>
    </div>
  );
}

/**
 * Small regime badge for the dashboard header.
 * Shows the overall market regime as a compact indicator.
 */
export function RegimeBadge({ data }: { data: RegimeResponse | undefined }) {
  if (!data) return null;

  const regime = data.summary.overall_regime;
  return (
    <div
      className={`flex items-center gap-1.5 px-2 py-0.5 rounded ${
        REGIME_BG[regime] || "bg-accent/15"
      }`}
    >
      <div
        className="w-1.5 h-1.5 rounded-full"
        style={{ backgroundColor: REGIME_COLORS[regime] || "#c8a84b" }}
      />
      <span
        className={`text-[10px] font-mono ${
          REGIME_TEXT[regime] || "text-accent"
        }`}
      >
        {data.summary.overall_display}
      </span>
    </div>
  );
}
