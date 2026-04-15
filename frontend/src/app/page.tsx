"use client";

export default function Home() {
  return (
    <div className="min-h-screen bg-bg">
      {/* ── Header ──────────────────────────────────────────────── */}
      <header className="border-b border-border px-6 py-4 flex items-center justify-between">
        <div className="flex items-center gap-3">
          <div className="w-2 h-2 rounded-full bg-accent" />
          <h1 className="font-display text-xl tracking-wide">
            Risk Monitor
          </h1>
          <span className="text-text-dim text-xs font-mono ml-2">
            S&P 500 · Société Générale · Siemens
          </span>
        </div>
        <div className="flex items-center gap-4">
          <span className="text-text-muted text-xs font-mono">
            Base: EUR
          </span>
          <div className="flex items-center gap-2">
            <div className="w-1.5 h-1.5 rounded-full bg-green-500 animate-pulse" />
            <span className="text-text-dim text-xs">Connected</span>
          </div>
        </div>
      </header>

      {/* ── Dashboard Grid ──────────────────────────────────────── */}
      <main className="p-6 grid grid-cols-12 gap-4">
        {/* Risk Overview Cards */}
        <MetricCard label="VaR 95%" value="—" col="col-span-3" />
        <MetricCard label="VaR 99%" value="—" col="col-span-3" />
        <MetricCard label="CVaR" value="—" col="col-span-3" />
        <MetricCard label="Drawdown" value="—" col="col-span-3" />

        {/* Volatility Chart placeholder */}
        <div className="col-span-8 h-80 rounded-lg bg-bg-2 border border-border gold-border flex items-center justify-center">
          <span className="text-text-muted font-mono text-sm">
            Rolling Volatility Chart
          </span>
        </div>

        {/* Correlation Matrix placeholder */}
        <div className="col-span-4 h-80 rounded-lg bg-bg-2 border border-border gold-border flex items-center justify-center">
          <span className="text-text-muted font-mono text-sm">
            Correlation Matrix
          </span>
        </div>

        {/* Drawdown Chart placeholder */}
        <div className="col-span-6 h-64 rounded-lg bg-bg-2 border border-border gold-border flex items-center justify-center">
          <span className="text-text-muted font-mono text-sm">
            Drawdown Over Time
          </span>
        </div>

        {/* Risk Contribution placeholder */}
        <div className="col-span-6 h-64 rounded-lg bg-bg-2 border border-border gold-border flex items-center justify-center">
          <span className="text-text-muted font-mono text-sm">
            Risk Contribution
          </span>
        </div>
      </main>
    </div>
  );
}

/* ── Metric Card Component ──────────────────────────────────────── */

function MetricCard({
  label,
  value,
  col,
}: {
  label: string;
  value: string;
  col: string;
}) {
  return (
    <div
      className={`${col} rounded-lg bg-bg-2 border border-border gold-border p-4 flex flex-col gap-1`}
    >
      <span className="text-text-muted text-xs font-mono uppercase tracking-widest">
        {label}
      </span>
      <span className="text-2xl font-display text-accent">{value}</span>
    </div>
  );
}
