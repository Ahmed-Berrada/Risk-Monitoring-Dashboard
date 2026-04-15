"use client";

import {
  type AnomalyResponse,
  TICKER_LABELS,
  TICKER_COLORS,
} from "@/lib/api";

interface Props {
  data: AnomalyResponse | undefined;
}

const SEVERITY_STYLES: Record<string, { bg: string; text: string; dot: string }> = {
  high: { bg: "bg-red-500/15", text: "text-red-400", dot: "bg-red-500" },
  medium: { bg: "bg-yellow-500/15", text: "text-yellow-400", dot: "bg-yellow-500" },
  low: { bg: "bg-blue-500/15", text: "text-blue-400", dot: "bg-blue-400" },
};

export default function AnomalyPanel({ data }: Props) {
  if (!data) {
    return (
      <div className="h-full flex items-center justify-center text-text-muted text-xs font-mono">
        Loading anomalies…
      </div>
    );
  }

  const { per_asset, cross_asset } = data;
  const tickers = Object.keys(per_asset).filter((t) => per_asset[t] !== null);

  // Collect all recent anomalies across assets, sorted by date desc
  const allRecent = tickers.flatMap((ticker) => {
    const asset = per_asset[ticker];
    if (!asset) return [];
    return asset.recent_anomalies.map((a) => ({
      ...a,
      ticker,
    }));
  });

  // Add cross-asset anomalies
  const crossRecent = (cross_asset?.recent || []).map((a) => ({
    date: a.date,
    return: Object.values(a.returns).reduce((s, v) => s + v, 0) / Object.keys(a.returns).length,
    score: a.score,
    severity: a.severity,
    ticker: "CROSS" as string,
  }));

  const combined = [...allRecent, ...crossRecent].sort(
    (a, b) => new Date(b.date).getTime() - new Date(a.date).getTime()
  );

  return (
    <div className="h-full flex flex-col px-3 pt-2 pb-2">
      {/* Header */}
      <div className="flex items-center justify-between mb-2">
        <span className="text-[10px] font-mono text-text-muted uppercase tracking-[0.15em]">
          Anomaly Detection
        </span>
        <span className="text-[9px] font-mono text-text-dim">
          Isolation Forest
        </span>
      </div>

      {/* Per-asset anomaly summary */}
      <div className="grid grid-cols-3 gap-2 mb-3">
        {tickers.map((ticker) => {
          const asset = per_asset[ticker]!;
          const isAnomaly = asset.latest_is_anomaly;

          return (
            <div
              key={ticker}
              className={`rounded-md border p-2 flex flex-col items-center ${
                isAnomaly
                  ? "border-red-500/40 bg-red-500/5"
                  : "border-border/30 bg-bg/50"
              }`}
            >
              <div className="flex items-center gap-1 mb-1">
                <div
                  className="w-1.5 h-1.5 rounded-full"
                  style={{ backgroundColor: TICKER_COLORS[ticker] }}
                />
                <span className="text-[9px] font-mono text-text-dim">
                  {TICKER_LABELS[ticker] || ticker}
                </span>
              </div>
              <span
                className={`text-xs font-mono ${
                  isAnomaly ? "text-red-400" : "text-green-400"
                }`}
              >
                {isAnomaly ? "⚠ Anomaly" : "Normal"}
              </span>
              <span className="text-[8px] font-mono text-text-muted mt-0.5">
                Score: {asset.latest_score.toFixed(3)}
              </span>
              <span className="text-[8px] font-mono text-text-muted">
                {asset.total_anomalies}/{asset.total_observations} flagged
              </span>
            </div>
          );
        })}
      </div>

      {/* Cross-asset status */}
      {cross_asset && (
        <div
          className={`rounded-md border p-1.5 mb-2 flex items-center justify-between ${
            cross_asset.latest_is_anomaly
              ? "border-red-500/40 bg-red-500/5"
              : "border-border/30 bg-bg/50"
          }`}
        >
          <span className="text-[9px] font-mono text-text-dim">
            Cross-Asset
          </span>
          <span
            className={`text-[9px] font-mono ${
              cross_asset.latest_is_anomaly ? "text-red-400" : "text-green-400"
            }`}
          >
            {cross_asset.latest_is_anomaly ? "⚠ Joint Anomaly" : "Normal"}
          </span>
          <span className="text-[8px] font-mono text-text-muted">
            {cross_asset.cross_asset_anomalies} total
          </span>
        </div>
      )}

      {/* Recent anomaly events */}
      <div className="flex-1 overflow-y-auto">
        <span className="text-[9px] font-mono text-text-muted uppercase tracking-wider block mb-1">
          Recent Events ({combined.length})
        </span>
        {combined.length === 0 ? (
          <div className="text-center text-text-muted text-[10px] font-mono py-4">
            No recent anomalies
          </div>
        ) : (
          <div className="space-y-1">
            {combined.slice(0, 8).map((event, i) => {
              const sev = SEVERITY_STYLES[event.severity] || SEVERITY_STYLES.low;

              return (
                <div
                  key={`${event.ticker}-${event.date}-${i}`}
                  className={`flex items-center justify-between rounded px-2 py-1 ${sev.bg}`}
                >
                  <div className="flex items-center gap-2">
                    <div className={`w-1 h-1 rounded-full ${sev.dot}`} />
                    <span className="text-[9px] font-mono text-text-dim">
                      {event.date}
                    </span>
                    <span
                      className="text-[9px] font-mono"
                      style={{
                        color:
                          event.ticker === "CROSS"
                            ? "#c8a84b"
                            : TICKER_COLORS[event.ticker] || "#ccc",
                      }}
                    >
                      {event.ticker === "CROSS"
                        ? "Cross"
                        : TICKER_LABELS[event.ticker] || event.ticker}
                    </span>
                  </div>
                  <div className="flex items-center gap-2">
                    <span
                      className={`text-[9px] font-mono ${
                        event.return < 0 ? "text-red-400" : "text-green-400"
                      }`}
                    >
                      {event.return >= 0 ? "+" : ""}
                      {(event.return * 100).toFixed(2)}%
                    </span>
                    <span className={`text-[8px] font-mono uppercase ${sev.text}`}>
                      {event.severity}
                    </span>
                  </div>
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}

/**
 * Small anomaly indicator for the dashboard header.
 */
export function AnomalyBadge({ data }: { data: AnomalyResponse | undefined }) {
  if (!data) return null;

  const hasAnomaly = Object.values(data.per_asset).some(
    (a) => a?.latest_is_anomaly
  );
  const crossAnomaly = data.cross_asset?.latest_is_anomaly;

  if (!hasAnomaly && !crossAnomaly) return null;

  return (
    <div className="flex items-center gap-1 px-2 py-0.5 rounded bg-red-500/15">
      <div className="w-1.5 h-1.5 rounded-full bg-red-500 animate-pulse" />
      <span className="text-[10px] font-mono text-red-400">Anomaly</span>
    </div>
  );
}
