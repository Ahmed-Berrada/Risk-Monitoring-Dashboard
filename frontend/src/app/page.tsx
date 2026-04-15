"use client";

import { useState } from "react";
import {
  useRiskSummary,
  useCorrelation,
  useContribution,
  usePortfolio,
  useRollingSeries,
  useGARCH,
  useRegimes,
  useAnomalies,
} from "@/lib/hooks";
import MetricCard, { getMetric } from "@/components/MetricCard";
import VolatilityChart from "@/components/VolatilityChart";
import DrawdownChart from "@/components/DrawdownChart";
import CorrelationHeatmap from "@/components/CorrelationHeatmap";
import RiskContributionChart from "@/components/RiskContributionChart";
import WeightsPanel from "@/components/WeightsPanel";
import AssetTable from "@/components/AssetTable";
import GARCHForecastChart from "@/components/GARCHForecastChart";
import RegimePanel, { RegimeBadge } from "@/components/RegimePanel";
import AnomalyPanel, { AnomalyBadge } from "@/components/AnomalyPanel";

export default function Home() {
  const { data: risk, isLoading: riskLoading } = useRiskSummary();
  const { data: correlation } = useCorrelation();
  const { data: contribution } = useContribution();
  const { data: portfolio } = usePortfolio();
  const { data: series } = useRollingSeries();
  const { data: garch } = useGARCH();
  const { data: regimes } = useRegimes();
  const { data: anomalies } = useAnomalies();

  const [volWindow, setVolWindow] = useState<"volatility_21d" | "volatility_63d">("volatility_21d");
  const [showTable, setShowTable] = useState(false);

  const metrics = risk?.metrics;

  // Portfolio-level metrics for the header cards
  const pVar95 = getMetric(metrics, "PORTFOLIO", "var_95");
  const pVar99 = getMetric(metrics, "PORTFOLIO", "var_99");
  const pCvar = getMetric(metrics, "PORTFOLIO", "cvar_95");
  const pDrawdown = getMetric(metrics, "PORTFOLIO", "current_drawdown");
  const pVol = getMetric(metrics, "PORTFOLIO", "volatility_21d");
  const pSharpe = getMetric(metrics, "PORTFOLIO", "sharpe_ratio");

  // Determine risk status color
  function ddStatus(dd: number | null): "green" | "amber" | "red" {
    if (dd === null) return "green";
    if (dd > 0.15) return "red";
    if (dd > 0.05) return "amber";
    return "green";
  }

  const asOf = risk?.as_of
    ? new Date(risk.as_of).toLocaleDateString("en-GB", {
        day: "2-digit",
        month: "short",
        year: "numeric",
      })
    : "—";

  return (
    <div className="min-h-screen bg-bg">
      {/* ── Header ──────────────────────────────────────────────── */}
      <header className="border-b border-border px-6 py-3 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-2 h-2 rounded-full bg-accent" />
          <h1 className="font-display text-xl tracking-wide">Risk Monitor</h1>
          <span className="text-text-dim text-xs font-mono ml-2">
            S&amp;P 500 · Société Générale · Siemens
          </span>
        </div>
        <div className="flex items-center gap-5">
          <RegimeBadge data={regimes} />
          <AnomalyBadge data={anomalies} />
          <span className="text-text-muted text-[10px] font-mono">
            As of {asOf}
          </span>
          <span className="text-text-muted text-[10px] font-mono">EUR</span>
          <div className="flex items-center gap-1.5">
            <div
              className={`w-1.5 h-1.5 rounded-full ${
                riskLoading ? "bg-yellow-500 animate-pulse" : "bg-green-500"
              }`}
            />
            <span className="text-text-dim text-[10px] font-mono">
              {riskLoading ? "Loading" : "Live"}
            </span>
          </div>
        </div>
      </header>

      {/* ── Dashboard ───────────────────────────────────────────── */}
      <main className="p-4 grid grid-cols-12 gap-3 max-w-[1600px] mx-auto">
        {/* ── Row 1: Portfolio KPI Cards ──────────────────────── */}
        <div className="col-span-2">
          <MetricCard
            label="VaR 95%"
            value={pVar95}
            subtitle="1-day"
          />
        </div>
        <div className="col-span-2">
          <MetricCard
            label="VaR 99%"
            value={pVar99}
            subtitle="1-day"
          />
        </div>
        <div className="col-span-2">
          <MetricCard
            label="CVaR 95%"
            value={pCvar}
            subtitle="Exp. Shortfall"
          />
        </div>
        <div className="col-span-2">
          <MetricCard
            label="Drawdown"
            value={pDrawdown}
            status={ddStatus(pDrawdown)}
            subtitle={
              pDrawdown !== null
                ? pDrawdown > 0.05
                  ? "Elevated"
                  : "Normal"
                : undefined
            }
          />
        </div>
        <div className="col-span-2">
          <MetricCard
            label="Volatility"
            value={pVol}
            subtitle="21-day ann."
          />
        </div>
        <div className="col-span-2">
          <MetricCard
            label="Sharpe"
            value={pSharpe}
            format="ratio"
            status={
              pSharpe !== null
                ? pSharpe > 1
                  ? "green"
                  : pSharpe > 0.5
                  ? "amber"
                  : "red"
                : "neutral"
            }
            subtitle="252-day"
          />
        </div>

        {/* ── Row 2: Volatility Chart + Weights ──────────────── */}
        <div className="col-span-9 h-80 rounded-lg bg-bg-2 border border-border gold-border overflow-hidden">
          <div className="flex items-center justify-between px-3 pt-2">
            <span className="text-[10px] font-mono text-text-muted uppercase tracking-[0.15em]">
              Rolling Volatility
            </span>
            <div className="flex gap-1">
              <button
                onClick={() => setVolWindow("volatility_21d")}
                className={`text-[9px] font-mono px-2 py-0.5 rounded transition-colors ${
                  volWindow === "volatility_21d"
                    ? "bg-accent/20 text-accent"
                    : "text-text-muted hover:text-text-dim"
                }`}
              >
                21d
              </button>
              <button
                onClick={() => setVolWindow("volatility_63d")}
                className={`text-[9px] font-mono px-2 py-0.5 rounded transition-colors ${
                  volWindow === "volatility_63d"
                    ? "bg-accent/20 text-accent"
                    : "text-text-muted hover:text-text-dim"
                }`}
              >
                63d
              </button>
            </div>
          </div>
          <div className="h-[calc(100%-28px)]">
            <VolatilityChart series={series} window={volWindow} />
          </div>
        </div>

        <div className="col-span-3 h-80 rounded-lg bg-bg-2 border border-border gold-border overflow-hidden">
          <WeightsPanel portfolio={portfolio} />
        </div>

        {/* ── Row 3: Drawdown + Correlation + Risk Contribution ── */}
        <div className="col-span-5 h-72 rounded-lg bg-bg-2 border border-border gold-border overflow-hidden">
          <div className="px-3 pt-2">
            <span className="text-[10px] font-mono text-text-muted uppercase tracking-[0.15em]">
              Drawdown
            </span>
          </div>
          <div className="h-[calc(100%-24px)]">
            <DrawdownChart series={series} />
          </div>
        </div>

        <div className="col-span-3 h-72 rounded-lg bg-bg-2 border border-border gold-border overflow-hidden">
          <CorrelationHeatmap data={correlation} />
        </div>

        <div className="col-span-4 h-72 rounded-lg bg-bg-2 border border-border gold-border overflow-hidden">
          <RiskContributionChart data={contribution} />
        </div>

        {/* ── Row 4: ML Insights ─────────────────────────────── */}
        <div className="col-span-5 h-[340px] rounded-lg bg-bg-2 border border-border gold-border overflow-hidden">
          <GARCHForecastChart data={garch} />
        </div>

        <div className="col-span-3 h-[340px] rounded-lg bg-bg-2 border border-border gold-border overflow-hidden">
          <RegimePanel data={regimes} />
        </div>

        <div className="col-span-4 h-[340px] rounded-lg bg-bg-2 border border-border gold-border overflow-hidden">
          <AnomalyPanel data={anomalies} />
        </div>

        {/* ── Row 5: Detailed Metrics Table ───────────────────── */}
        <div className="col-span-12 rounded-lg bg-bg-2 border border-border gold-border overflow-hidden">
          <button
            onClick={() => setShowTable(!showTable)}
            className="w-full flex items-center justify-between px-4 py-2.5 hover:bg-bg-3/50 transition-colors"
          >
            <span className="text-[10px] font-mono text-text-muted uppercase tracking-[0.15em]">
              Detailed Metrics
            </span>
            <span className="text-text-muted text-xs">
              {showTable ? "▲" : "▼"}
            </span>
          </button>
          {showTable && (
            <div className="px-2 pb-3">
              <AssetTable metrics={metrics} />
            </div>
          )}
        </div>
      </main>
    </div>
  );
}
