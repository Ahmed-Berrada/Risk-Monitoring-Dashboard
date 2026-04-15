"""API client for the Risk Monitoring Dashboard backend."""

const API_BASE = process.env.NEXT_PUBLIC_API_URL || "http://localhost:8000";

export interface HealthResponse {
  status: string;
  env: string;
  tickers: string[];
  base_currency: string;
}

export interface IngestionResult {
  status: string;
  results: Record<
    string,
    { status: string; rows?: number; error?: string }
  >;
}

export async function fetchHealth(): Promise<HealthResponse> {
  const res = await fetch(`${API_BASE}/health`);
  if (!res.ok) throw new Error(`Health check failed: ${res.status}`);
  return res.json();
}

export async function triggerIngestion(): Promise<IngestionResult> {
  const res = await fetch(`${API_BASE}/api/ingestion/run`, {
    method: "POST",
  });
  if (!res.ok) throw new Error(`Ingestion failed: ${res.status}`);
  return res.json();
}

export async function triggerBackfill(
  years: number = 5
): Promise<IngestionResult> {
  const res = await fetch(
    `${API_BASE}/api/ingestion/backfill?years=${years}`,
    { method: "POST" }
  );
  if (!res.ok) throw new Error(`Backfill failed: ${res.status}`);
  return res.json();
}
