"use client";

import { useState, useCallback } from "react";
import { updateWeights, tickerLabel, type PortfolioData } from "@/lib/api";
import { mutate } from "swr";

interface WeightsPanelProps {
  portfolio: PortfolioData | undefined;
}

export default function WeightsPanel({ portfolio }: WeightsPanelProps) {
  const tickers = portfolio?.tickers || [];
  const currentWeights = portfolio?.weights || {};

  const [weights, setWeights] = useState<Record<string, number>>(currentWeights);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  // Sync when portfolio data arrives
  const hasInit = Object.keys(weights).length > 0;
  if (!hasInit && Object.keys(currentWeights).length > 0) {
    setWeights({ ...currentWeights });
  }

  const total = Object.values(weights).reduce((a, b) => a + b, 0);
  const isValid = Math.abs(total - 1.0) < 0.01;

  const handleChange = (ticker: string, value: number) => {
    setWeights((prev) => ({ ...prev, [ticker]: value }));
    setError(null);
  };

  const handleSave = useCallback(async () => {
    if (!isValid) {
      setError("Weights must sum to 100%");
      return;
    }
    setSaving(true);
    setError(null);
    try {
      await updateWeights(weights);
      // Revalidate all dependent data
      await Promise.all([
        mutate("risk-summary"),
        mutate("contribution"),
        mutate("rolling-series"),
        mutate("portfolio"),
        mutate("correlation"),
      ]);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Failed to update");
    } finally {
      setSaving(false);
    }
  }, [weights, isValid]);

  const handleReset = () => {
    const n = tickers.length;
    const eq: Record<string, number> = {};
    tickers.forEach((t, i) => {
      eq[t] = i === n - 1 ? +(1 - (n - 1) * +(1 / n).toFixed(4)).toFixed(4) : +(1 / n).toFixed(4);
    });
    setWeights(eq);
    setError(null);
  };

  return (
    <div className="flex flex-col h-full p-3 gap-3">
      <div className="text-[10px] font-mono text-text-muted uppercase tracking-[0.15em]">
        Portfolio Weights
      </div>

      <div className="flex flex-col gap-2.5 flex-1">
        {tickers.map((ticker) => (
          <div key={ticker} className="flex items-center gap-2">
            <span className="text-xs font-mono text-text-dim w-16 truncate">
              {tickerLabel(ticker)}
            </span>
            <input
              type="range"
              min={0}
              max={100}
              step={1}
              value={Math.round((weights[ticker] || 0) * 100)}
              onChange={(e) =>
                handleChange(ticker, parseInt(e.target.value) / 100)
              }
              className="flex-1 accent-accent h-1 bg-bg-3 rounded-lg appearance-none cursor-pointer"
            />
            <span className="text-xs font-mono text-accent w-12 text-right">
              {((weights[ticker] || 0) * 100).toFixed(0)}%
            </span>
          </div>
        ))}
      </div>

      {/* Sum indicator */}
      <div
        className={`text-[10px] font-mono text-center py-1 rounded ${
          isValid
            ? "text-green-400 bg-green-500/10"
            : "text-red-400 bg-red-500/10"
        }`}
      >
        Total: {(total * 100).toFixed(1)}%{" "}
        {isValid ? "✓" : "— must equal 100%"}
      </div>

      {error && (
        <div className="text-[10px] font-mono text-red-400 text-center">
          {error}
        </div>
      )}

      <div className="flex gap-2">
        <button
          onClick={handleReset}
          className="flex-1 text-[10px] font-mono py-1.5 rounded border border-border text-text-dim hover:text-text hover:border-border-2 transition-colors"
        >
          Equal
        </button>
        <button
          onClick={handleSave}
          disabled={!isValid || saving}
          className={`flex-1 text-[10px] font-mono py-1.5 rounded transition-colors ${
            isValid && !saving
              ? "bg-accent/20 text-accent border border-accent/30 hover:bg-accent/30"
              : "bg-bg-3 text-text-muted border border-border cursor-not-allowed"
          }`}
        >
          {saving ? "Computing..." : "Apply"}
        </button>
      </div>
    </div>
  );
}
