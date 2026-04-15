/** API client for the Risk Monitoring Dashboard backend. */

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

// ── Types ───────────────────────────────────────────────────────────────────

export interface HealthResponse {
  status: string;
  env: string;
  tickers: string[];
  base_currency: string;
}

export interface MetricValue {
  ticker: string | null;
  metric_name: string;
  value: number;
  window_days: number | null;
}

export interface RiskSummary {
  as_of: string;
  metrics: MetricValue[];
}

export interface CorrelationData {
  as_of: string;
  matrix: Record<string, Record<string, number>>;
  tickers: string[];
}

export interface RiskContribution {
  as_of: string;
  contributions: Record<string, number>;
}

export interface PortfolioData {
  weights: Record<string, number>;
  tickers: string[];
}

export interface TimeSeriesData {
  dates: string[];
  values: number[];
}

export interface AssetSeries {
  volatility_21d: TimeSeriesData;
  volatility_63d: TimeSeriesData;
  drawdown: TimeSeriesData;
  sharpe_rolling: TimeSeriesData;
}

export interface RollingSeries {
  [ticker: string]: AssetSeries | Record<string, TimeSeriesData>;
}

// ── Ticker display helpers ──────────────────────────────────────────────────

export const TICKER_LABELS: Record<string, string> = {
  "^GSPC": "S&P 500",
  "GLE.PA": "Soc Gen",
  "SIE.DE": "Siemens",
  PORTFOLIO: "Portfolio",
};

export const TICKER_COLORS: Record<string, string> = {
  "^GSPC": "#60a5fa",   // blue
  "GLE.PA": "#f97316",  // orange
  "SIE.DE": "#a78bfa",  // purple
  PORTFOLIO: "#c8a84b", // gold/accent
};

export function tickerLabel(ticker: string): string {
  return TICKER_LABELS[ticker] || ticker;
}

// ── API Functions ───────────────────────────────────────────────────────────

async function apiFetch<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, init);
  if (!res.ok) {
    const text = await res.text().catch(() => "");
    throw new Error(`API ${path} failed (${res.status}): ${text}`);
  }
  return res.json();
}

export const fetchHealth = () => apiFetch<HealthResponse>("/health");

export const fetchRiskSummary = () =>
  apiFetch<RiskSummary>("/api/risk/summary");

export const fetchCorrelation = () =>
  apiFetch<CorrelationData>("/api/risk/correlation");

export const fetchContribution = () =>
  apiFetch<RiskContribution>("/api/risk/contribution");

export const fetchPortfolio = () =>
  apiFetch<PortfolioData>("/api/portfolio");

export const fetchRollingSeries = () =>
  apiFetch<RollingSeries>("/api/risk/series");

export const computeRisk = () =>
  apiFetch<{ status: string }>("/api/risk/compute", { method: "POST" });

export const updateWeights = (weights: Record<string, number>) =>
  apiFetch<{ status: string; weights: Record<string, number>; risk_recomputed: boolean }>(
    "/api/portfolio/weights",
    {
      method: "PUT",
      headers: { "Content-Type": "application/json" },
      body: JSON.stringify({ weights }),
    }
  );

// ── ML Types ────────────────────────────────────────────────────────────────

export interface GARCHParams {
  omega: number;
  alpha: number;
  beta: number;
  persistence: number;
}

export interface GARCHForecast {
  forecast_vol: number[];
  current_vol: number;
  params: GARCHParams;
  horizon_days: number;
}

export interface GARCHResult {
  forecast: GARCHForecast;
  conditional_vol: TimeSeriesData;
  aic: number;
  bic: number;
}

export interface GARCHResponse {
  forecasts: Record<string, GARCHResult | null>;
}

export interface RegimeStat {
  regime: string;
  display: string;
  mean_return: number;
  volatility: number;
  frequency: number;
  n_days: number;
}

export interface RegimeAsset {
  current_regime: string;
  current_regime_display: string;
  regime_stats: RegimeStat[];
  transitions: Record<string, Record<string, number>>;
  regime_series: {
    dates: string[];
    regimes: number[];
    labels: string[];
  };
  n_regimes: number;
  log_likelihood: number;
}

export interface RegimeSummary {
  overall_regime: string;
  overall_display: string;
  per_asset: Record<string, { regime: string; display: string }>;
}

export interface RegimeResponse {
  per_asset: Record<string, RegimeAsset | null>;
  summary: RegimeSummary;
}

export interface AnomalyEvent {
  date: string;
  return: number;
  score: number;
  severity: "high" | "medium" | "low";
}

export interface AnomalyAsset {
  total_anomalies: number;
  total_observations: number;
  anomaly_rate: number;
  recent_anomalies: AnomalyEvent[];
  score_series: {
    dates: string[];
    scores: number[];
    is_anomaly: boolean[];
  };
  latest_score: number;
  latest_is_anomaly: boolean;
}

export interface CrossAssetAnomaly {
  date: string;
  returns: Record<string, number>;
  score: number;
  severity: "high" | "medium" | "low";
}

export interface AnomalyResponse {
  per_asset: Record<string, AnomalyAsset | null>;
  cross_asset: {
    cross_asset_anomalies: number;
    recent: CrossAssetAnomaly[];
    latest_score: number;
    latest_is_anomaly: boolean;
  } | null;
}

// ── ML API Functions ────────────────────────────────────────────────────────

export const fetchGARCH = () =>
  apiFetch<GARCHResponse>("/api/ml/garch");

export const fetchRegimes = () =>
  apiFetch<RegimeResponse>("/api/ml/regimes");

export const fetchAnomalies = () =>
  apiFetch<AnomalyResponse>("/api/ml/anomalies");

export const computeML = () =>
  apiFetch<{ status: string; computed_at: string }>("/api/ml/compute", { method: "POST" });
