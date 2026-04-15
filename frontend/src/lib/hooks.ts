/** SWR hooks for data fetching with automatic revalidation. */

"use client";

import useSWR from "swr";
import {
  fetchRiskSummary,
  fetchCorrelation,
  fetchContribution,
  fetchPortfolio,
  fetchRollingSeries,
  fetchHealth,
  fetchGARCH,
  fetchRegimes,
  fetchAnomalies,
  type RiskSummary,
  type CorrelationData,
  type RiskContribution,
  type PortfolioData,
  type RollingSeries,
  type HealthResponse,
  type GARCHResponse,
  type RegimeResponse,
  type AnomalyResponse,
} from "./api";

const REFRESH_INTERVAL = 60_000; // 60s

export function useHealth() {
  return useSWR<HealthResponse>("health", fetchHealth, {
    refreshInterval: REFRESH_INTERVAL,
  });
}

export function useRiskSummary() {
  return useSWR<RiskSummary>("risk-summary", fetchRiskSummary, {
    refreshInterval: REFRESH_INTERVAL,
  });
}

export function useCorrelation() {
  return useSWR<CorrelationData>("correlation", fetchCorrelation, {
    refreshInterval: REFRESH_INTERVAL,
  });
}

export function useContribution() {
  return useSWR<RiskContribution>("contribution", fetchContribution, {
    refreshInterval: REFRESH_INTERVAL,
  });
}

export function usePortfolio() {
  return useSWR<PortfolioData>("portfolio", fetchPortfolio, {
    refreshInterval: REFRESH_INTERVAL,
  });
}

export function useRollingSeries() {
  return useSWR<RollingSeries>("rolling-series", fetchRollingSeries, {
    refreshInterval: REFRESH_INTERVAL,
  });
}

// ── ML Hooks ────────────────────────────────────────────────────────────────

const ML_REFRESH = 300_000; // 5 min (ML models are heavier)

export function useGARCH() {
  return useSWR<GARCHResponse>("garch", fetchGARCH, {
    refreshInterval: ML_REFRESH,
    revalidateOnFocus: false,
  });
}

export function useRegimes() {
  return useSWR<RegimeResponse>("regimes", fetchRegimes, {
    refreshInterval: ML_REFRESH,
    revalidateOnFocus: false,
  });
}

export function useAnomalies() {
  return useSWR<AnomalyResponse>("anomalies", fetchAnomalies, {
    refreshInterval: ML_REFRESH,
    revalidateOnFocus: false,
  });
}
