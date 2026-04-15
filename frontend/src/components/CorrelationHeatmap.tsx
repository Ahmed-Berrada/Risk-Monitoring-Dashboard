"use client";

import { type CorrelationData, tickerLabel } from "@/lib/api";

interface CorrelationHeatmapProps {
  data: CorrelationData | undefined;
}

function getCellColor(value: number): string {
  // Diverging color scale: -1 (red) → 0 (dark) → +1 (gold)
  if (value >= 0.8) return "bg-accent/80 text-bg";
  if (value >= 0.6) return "bg-accent/50 text-text";
  if (value >= 0.4) return "bg-accent/30 text-text";
  if (value >= 0.2) return "bg-accent/15 text-text-dim";
  if (value >= 0) return "bg-bg-3 text-text-muted";
  if (value >= -0.2) return "bg-red-900/20 text-text-muted";
  if (value >= -0.5) return "bg-red-900/40 text-red-300";
  return "bg-red-900/60 text-red-200";
}

export default function CorrelationHeatmap({ data }: CorrelationHeatmapProps) {
  if (!data) {
    return (
      <div className="w-full h-full flex items-center justify-center">
        <span className="text-text-muted font-mono text-sm animate-pulse">
          Correlation — loading...
        </span>
      </div>
    );
  }

  const { tickers, matrix } = data;

  return (
    <div className="flex flex-col h-full justify-center px-3 py-2">
      <div className="text-[10px] font-mono text-text-muted uppercase tracking-[0.15em] mb-3">
        63-Day Rolling Correlation
      </div>

      <div className="grid gap-1" style={{ gridTemplateColumns: `auto repeat(${tickers.length}, 1fr)` }}>
        {/* Empty top-left cell */}
        <div />

        {/* Column headers */}
        {tickers.map((t) => (
          <div
            key={`col-${t}`}
            className="text-[10px] font-mono text-text-dim text-center truncate px-1"
          >
            {tickerLabel(t)}
          </div>
        ))}

        {/* Rows */}
        {tickers.map((rowTicker) => (
          <>
            {/* Row header */}
            <div
              key={`row-${rowTicker}`}
              className="text-[10px] font-mono text-text-dim flex items-center pr-2 truncate"
            >
              {tickerLabel(rowTicker)}
            </div>

            {/* Cells */}
            {tickers.map((colTicker) => {
              const val = matrix[rowTicker]?.[colTicker] ?? 0;
              const isDiag = rowTicker === colTicker;
              return (
                <div
                  key={`${rowTicker}-${colTicker}`}
                  className={`
                    rounded aspect-square flex items-center justify-center
                    font-mono text-xs transition-all
                    ${isDiag ? "bg-accent/10 text-accent/50" : getCellColor(val)}
                  `}
                  title={`${tickerLabel(rowTicker)} × ${tickerLabel(colTicker)}: ${val.toFixed(3)}`}
                >
                  {val.toFixed(2)}
                </div>
              );
            })}
          </>
        ))}
      </div>

      {/* Color legend */}
      <div className="flex items-center gap-2 mt-3 justify-center">
        <span className="text-[9px] font-mono text-text-muted">-1</span>
        <div className="flex h-2 rounded overflow-hidden flex-1 max-w-[120px]">
          <div className="flex-1 bg-red-900/60" />
          <div className="flex-1 bg-red-900/20" />
          <div className="flex-1 bg-bg-3" />
          <div className="flex-1 bg-accent/30" />
          <div className="flex-1 bg-accent/60" />
        </div>
        <span className="text-[9px] font-mono text-text-muted">+1</span>
      </div>
    </div>
  );
}
