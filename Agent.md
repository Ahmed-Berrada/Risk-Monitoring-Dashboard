# Risk Monitoring Dashboard — Architecture & Plan

## Overview

A **hybrid modular monolith** FastAPI backend structured as logical services (data-ingestion, risk-engine, alerting, API) with event-driven internal communication, a Next.js frontend, TimescaleDB for time-series storage, and end-of-day data from yfinance. Portfolio denominated in **EUR** with **user-configurable weights**.

**Assets:**
| Asset | Ticker | Exchange | Currency |
|-------|--------|----------|----------|
| S&P 500 | `^GSPC` | NYSE | USD (converted to EUR) |
| Société Générale | `GLE.PA` | Euronext Paris | EUR |
| Siemens | `SIE.DE` | Frankfurt | EUR |

---

## Architecture Decisions

### 1. Hybrid Modular Monolith (not Microservices + Kafka)

**Decision:** Structure code as logical services within a single FastAPI deployable, with event-driven internal communication via PostgreSQL `LISTEN/NOTIFY` and SSE to the frontend.

**Rationale:**
- At this scale (3 assets, single user), Kafka is severe overkill — it's designed for millions of messages/second across distributed consumers. We produce < 1 msg/second.
- Full microservices add operational overhead (service discovery, distributed tracing, network partitions, separate deploys) with no benefit at this scale.
- A modular monolith with clear service boundaries gives the same **code organization** benefits as microservices without the infrastructure tax.
- Real trading desks use **event-driven** communication (market data → risk computation → alerts), which is an orthogonal concern to deployment topology. We get the event-driven pattern without Kafka.
- Services can be **extracted later** if the system grows — this is the industry-recommended evolutionary architecture path (Martin Fowler, Sam Newman).

**What we use instead of Kafka:**
| Communication | Technology | Why |
|--------------|------------|-----|
| DB → Backend (new data arrived) | PostgreSQL `LISTEN/NOTIFY` | Zero infrastructure, built into our DB |
| Backend → Frontend (push updates) | Server-Sent Events (SSE) | HTTP-native, auto-reconnect, one-directional is sufficient |
| Frontend → Backend (weight changes, queries) | REST API | Standard request-response for user actions |
| Caching | Redis | Optional, for computed metric caching |

**Service boundaries in code:**
```
backend/
├── services/
│   ├── ingestion/      # Data fetching, cleaning, storage
│   ├── fx/             # EUR/USD conversion
│   ├── risk_engine/    # All risk metric computations
│   ├── portfolio/      # Weight management
│   ├── ml/             # GARCH, HMM, anomaly detection
│   ├── alerting/       # Threshold monitoring, notifications
│   └── stress_test/    # Historical scenario analysis
├── api/                # FastAPI routers (thin layer over services)
├── models/             # SQLAlchemy/Pydantic models
├── events/             # Internal event bus (LISTEN/NOTIFY wrapper)
└── config/             # Settings, scheduling
```

### 2. End-of-Day Data Frequency

**Decision:** Fetch daily OHLCV data once after market close.

**Rationale:**
- yfinance is reliable and free for daily data with decades of history.
- Intraday data (< 1d intervals) is only available for the last 60 days in yfinance — insufficient for risk computation.
- Intraday would push us toward paid APIs (Polygon.io, IEX Cloud) for no meaningful risk insight gain on a daily-rebalanced portfolio.
- Industry standard for portfolio risk monitoring is end-of-day for non-HFT use cases.

**Schedule:**
- EU markets close at 17:30 CET → fetch `GLE.PA`, `SIE.DE`
- US markets close at 22:00 CET → fetch `^GSPC`, `EURUSD=X`
- Full risk recomputation triggered after US close (all data available)

### 3. EUR Base Currency

**Decision:** All portfolio risk metrics computed in EUR. S&P 500 returns converted from USD to EUR using daily EUR/USD rates.

**Rationale:**
- 2 of 3 assets are EUR-denominated (GLE.PA, SIE.DE)
- Provides a realistic view of FX-adjusted risk for a European investor
- FX risk on S&P 500 position is captured in the risk metrics (which is correct — it's real risk)

**Implementation:**
- Fetch `EURUSD=X` daily rate from yfinance
- Convert S&P 500 prices: `price_eur = price_usd / eurusd_rate`
- Store both original and converted prices
- All return calculations use EUR-denominated prices

### 4. TimescaleDB over Plain PostgreSQL

**Decision:** Use TimescaleDB extension on PostgreSQL.

**Rationale:**
- TimescaleDB is a PostgreSQL extension, not a separate database — same connection string, same SQL, same tooling. Overhead is near-zero.
- **Hypertables** auto-partition time-series data by time → efficient queries on recent data.
- **Continuous aggregates** pre-compute rolling metric summaries automatically and incrementally — directly maps to our need for multi-window risk metrics.
- **Columnar compression** on historical data (up to 98% compression on old OHLCV data).
- Industry-standard for financial time-series workloads.

### 5. Historical Simulation VaR (Primary Method)

**Decision:** Use historical simulation as the primary VaR method. Add GARCH-enhanced parametric VaR via the ML layer.

**Rationale:**
- No distributional assumptions (doesn't assume returns are normal — they aren't).
- With 5+ years of daily data (~1,260 observations per asset), we have sufficient sample size.
- For 3 assets, computational cost is trivial.
- Always paired with CVaR (Expected Shortfall) to capture tail risk that VaR misses.
- GARCH-enhanced VaR added later provides forward-looking volatility estimates.

### 6. User-Configurable Portfolio Weights

**Decision:** Weights are user-configurable via the dashboard, defaulting to equal-weight (1/3 each).

**Rationale:**
- More realistic than fixed weights — allows scenario exploration ("what if I overweight Siemens?")
- Weight changes trigger immediate risk recomputation
- Weight history stored for audit trail

---

## Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| Frontend | Next.js (TypeScript) | Dashboard UI, charts, SSE client |
| Backend | FastAPI (Python) | REST API, risk computations, scheduling |
| Database | TimescaleDB (PostgreSQL extension) | OHLCV storage, risk metric history |
| Cache | Redis | Computed metric caching (optional) |
| Data Source | yfinance | Daily OHLCV + FX rates |
| Scheduling | APScheduler | Timed data ingestion |
| ML | `arch` (GARCH), `hmmlearn` (HMM), `scikit-learn` (anomaly detection) | Volatility forecasting, regime detection |
| Charts | Recharts or Lightweight Charts | Financial charts in the frontend |
| Infra | Docker Compose | Local dev: TimescaleDB + Redis + Backend + Frontend |

---

## Implementation Plan

### Phase 1 — Foundation & Data Pipeline

#### 1.1 Project Scaffolding
- Create `backend/` with FastAPI, Poetry/uv, modular service structure
- Create `frontend/` with Next.js + TypeScript
- Write `docker-compose.yml`: TimescaleDB, Redis, backend, frontend containers
- Configure environment variables, `.env.example`

#### 1.2 TimescaleDB Schema
```sql
-- Hypertable: raw OHLCV data
CREATE TABLE ohlcv_daily (
    time        TIMESTAMPTZ NOT NULL,
    ticker      TEXT NOT NULL,
    open        DOUBLE PRECISION,
    high        DOUBLE PRECISION,
    low         DOUBLE PRECISION,
    close       DOUBLE PRECISION,
    adj_close   DOUBLE PRECISION,
    volume      BIGINT,
    currency    TEXT NOT NULL
);
SELECT create_hypertable('ohlcv_daily', 'time');

-- FX rates
CREATE TABLE fx_rates (
    time        TIMESTAMPTZ NOT NULL,
    pair        TEXT NOT NULL,       -- e.g. 'EURUSD'
    rate        DOUBLE PRECISION NOT NULL
);
SELECT create_hypertable('fx_rates', 'time');

-- Computed risk metrics
CREATE TABLE risk_metrics (
    time        TIMESTAMPTZ NOT NULL,
    ticker      TEXT,                -- NULL = portfolio-level
    metric_name TEXT NOT NULL,       -- 'var_95', 'cvar_99', 'volatility_21d', etc.
    value       DOUBLE PRECISION NOT NULL,
    window_days INT,
    weights     JSONB                -- portfolio weights snapshot
);
SELECT create_hypertable('risk_metrics', 'time');

-- Portfolio weights
CREATE TABLE portfolio_weights (
    id          SERIAL PRIMARY KEY,
    weights     JSONB NOT NULL,      -- {"^GSPC": 0.33, "GLE.PA": 0.33, "SIE.DE": 0.34}
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    is_active   BOOLEAN DEFAULT TRUE
);

-- Alerts configuration
CREATE TABLE alert_rules (
    id          SERIAL PRIMARY KEY,
    metric_name TEXT NOT NULL,
    ticker      TEXT,                -- NULL = portfolio-level
    operator    TEXT NOT NULL,       -- 'gt', 'lt', 'gte', 'lte'
    threshold   DOUBLE PRECISION NOT NULL,
    severity    TEXT NOT NULL,       -- 'warning', 'breach'
    is_active   BOOLEAN DEFAULT TRUE
);

-- Alert history
CREATE TABLE alert_events (
    time        TIMESTAMPTZ NOT NULL,
    rule_id     INT REFERENCES alert_rules(id),
    metric_value DOUBLE PRECISION,
    message     TEXT
);
SELECT create_hypertable('alert_events', 'time');
```

#### 1.3 Data Ingestion Service
- Scheduled job (APScheduler) running after market close
- Fetches OHLCV from yfinance for `^GSPC`, `GLE.PA`, `SIE.DE`, `EURUSD=X`
- **Data quality guards:**
  - Null/zero value checks on OHLCV fields
  - Stale data detection (same price repeating = market closed or data stuck)
  - Reasonable bound validation (flag single-day moves > 20%)
  - Volume sanity checks
- Stores validated data in TimescaleDB
- Emits `DataRefreshed` event via PostgreSQL `NOTIFY`
- Backfill CLI command: `python -m backend.cli backfill --years 5`

#### 1.4 FX Conversion Layer
- Convert S&P 500 prices: `price_eur = price_usd / eurusd_rate`
- Store both original (USD) and converted (EUR) prices
- Handle missing FX rates (weekends, holidays) by forward-filling last known rate

---

### Phase 2 — Risk Engine

#### 2.1 Core Risk Metrics
Computed for each individual asset AND the weighted portfolio:

| Metric | Method | Parameters |
|--------|--------|------------|
| **VaR (95%, 99%)** | Historical simulation | 252-day lookback |
| **CVaR / Expected Shortfall** | Mean of losses beyond VaR threshold | 252-day lookback |
| **Rolling Volatility** | Annualized std of returns × √252 | 21-day and 63-day windows |
| **Maximum Drawdown** | Peak-to-trough decline | Full history |
| **Current Drawdown** | Current level vs all-time high | Point-in-time |
| **Sharpe Ratio** | (Return - Rf) / σ | Rolling 252-day, Rf from ECB rate |
| **Sortino Ratio** | (Return - Rf) / downside σ | Rolling 252-day |
| **Correlation Matrix** | Pairwise Pearson correlation | Rolling 63-day |
| **Beta** | Covariance with S&P / Variance of S&P | Rolling 252-day |
| **Risk Contribution** | Marginal VaR × weight per asset | Current weights |
| **Tracking Error** | Std of return difference vs benchmark | Rolling 252-day |

#### 2.2 Weight Management
- CRUD endpoints for portfolio weights
- Default: `{"^GSPC": 0.3333, "GLE.PA": 0.3333, "SIE.DE": 0.3334}`
- Weight change triggers immediate risk recomputation
- Weight history stored in `portfolio_weights` table

#### 2.3 Event Flow
```
NOTIFY 'data_refreshed'
    → Risk Engine listens
    → Fetches latest OHLCV + current weights
    → Computes all metrics
    → Stores in risk_metrics table
    → NOTIFY 'risk_updated'
    → Alert service evaluates thresholds
    → SSE pushes update to frontend
```

---

### Phase 3 — AI/ML Layer ✅ IMPLEMENTED

#### 3.1 Volatility Forecasting (GARCH) ✅
- **GARCH(1,1)** model per asset using `arch` library with Student-t error distribution
- Produces **10-day ahead** annualised volatility forecasts
- Extracts full conditional volatility series for plotting
- Model parameters exposed: ω, α, β, persistence (α+β)
- S&P 500 persistence ~0.98 (high volatility clustering, typical for equity indices)
- API: `GET /api/ml/garch`

#### 3.2 Regime Detection (HMM) ✅
- **Gaussian HMM** with 3 states using `hmmlearn` (Viterbi decoding)
- Features: [daily_return, |daily_return|] — captures direction and magnitude
- States sorted by volatility: **Calm** (low_vol), **Normal** (medium_vol), **Stressed** (high_vol)
- Per-regime statistics: annualised return, volatility, frequency, transition matrix
- Full regime time series for plotting
- Aggregate "overall market regime" across all assets
- Dashboard header shows regime badge (color-coded)
- API: `GET /api/ml/regimes`

#### 3.3 Anomaly Detection ✅
- **Isolation Forest** (`scikit-learn`, 200 estimators, 2% contamination) per asset
- 5 features: daily_return, |return|, return², rolling_5d_return, rolling_5d_std
- **Cross-asset anomaly detection**: joint feature space with pairwise return spreads
- Anomaly score series for charting, severity classification (high/medium/low)
- Recent anomaly event feed with date, return, score, severity
- Dashboard header shows anomaly alert badge when anomalies detected
- API: `GET /api/ml/anomalies`

#### 3.4 ML Integration ✅
- Event pipeline: `data_refreshed` → risk computation → ML model re-run (automatic)
- ML orchestrator runs all 3 models via `run_all_models()`
- Frontend: SWR hooks with 5-minute refresh interval (heavier computation)
- 3 new dashboard components: GARCH forecast chart, Regime panel, Anomaly panel

---

### Phase 4 — API & Frontend

#### 4.1 REST API Endpoints

```
GET  /api/portfolio                              → Current weights, positions, value
PUT  /api/portfolio/weights                      → Update weights → trigger recompute

GET  /api/risk/summary                           → All current risk metrics (latest)
GET  /api/risk/history?metric=var_95&days=252    → Historical metric time series
GET  /api/risk/correlation                       → Current correlation matrix (3×3)
GET  /api/risk/contribution                      → Risk contribution per asset
GET  /api/risk/stress-test?scenario=covid        → Stress test results

GET  /api/alerts                                 → Active alerts
POST /api/alerts/rules                           → Create alert rule
PUT  /api/alerts/rules/{id}                      → Update alert rule

GET  /api/ml/regime                              → Current regime + probabilities
GET  /api/ml/volatility-forecast                 → GARCH forecasts per asset

SSE  /api/stream                                 → Real-time push when new data/metrics arrive
```

#### 4.2 Next.js Dashboard Layout

**Header Bar:**
- Portfolio value (EUR), last updated timestamp
- Current regime badge (green = low-vol, amber = high-vol, red = crisis)
- Data freshness indicator per ticker

**Risk Overview Cards (top row):**
- VaR 95% / VaR 99% with sparkline
- CVaR with sparkline
- Current drawdown with traffic-light color
- Rolling volatility (21d) with trend arrow
- Sharpe ratio

**Charts Section (middle):**
- Rolling volatility over time (21d + 63d) — line chart
- Drawdown over time — area chart (inverted)
- VaR evolution — line chart with confidence bands
- Individual asset price series (EUR-denominated) — candlestick or line

**Correlation & Contribution (side by side):**
- 3×3 correlation heatmap with color gradient
- Risk contribution horizontal bar chart (which asset drives risk)

**Portfolio Configuration Panel:**
- Weight sliders/inputs per asset (sum must = 100%)
- "Apply" button → triggers recomputation → dashboard updates via SSE

**Alerts Panel:**
- Active alerts list with severity badge (warning/breach)
- Threshold configuration form
- Historical percentile context: "VaR is at 92nd percentile of last 252 days"

**Stress Testing View:**
- Scenario selector: 2008 GFC, 2011 EU Debt, 2020 COVID, 2022 Rate Hikes, Custom
- Projected portfolio loss under scenario
- Per-asset impact breakdown

---

### Phase 5 — Alerting & Decision Support

#### 5.1 Alerting Service
- Evaluates all active `alert_rules` after each risk computation
- Two-tier severity: **warning** (amber) and **breach** (red)
- Example rules:
  - Portfolio VaR (99%) > €X → breach
  - Drawdown > 10% → warning, > 20% → breach
  - Correlation between GLE.PA and SIE.DE drops below 0.2 → warning
  - Rolling volatility exits 2σ of its own 252-day distribution → warning
- Delivery: SSE to dashboard (primary), email/webhook (optional future)
- Each metric displayed with its **historical percentile rank** for context

#### 5.2 Stress Testing Engine
- Pre-defined scenarios using actual historical returns during crisis periods:
  - **2008 GFC** (Sep-Nov 2008): Apply realized daily returns from that period
  - **2011 EU Debt Crisis** (Jul-Sep 2011)
  - **2020 COVID Crash** (Feb-Mar 2020)
  - **2022 Rate Hike Cycle** (Jan-Oct 2022)
- Custom scenario: User inputs shock % per asset
- Output: Projected portfolio loss, per-asset loss, max drawdown under scenario

---

### Phase 6 — Polish & DevOps

- Full `README.md` with architecture diagram, setup guide, API reference
- Data quality dashboard page (data freshness, ingestion history, anomalies)
- `docker-compose up` brings up full working stack
- Health check endpoints
- Logging (structured JSON logs via `structlog`)
- Error handling and graceful degradation (if yfinance is down, serve stale data with warning)

---

## Verification Strategy

| Type | Tool | What |
|------|------|------|
| Unit tests | `pytest` | Risk metric computations against known datasets (fixed return series → assert exact VaR/vol) |
| Integration tests | `pytest` + `httpx` | Full pipeline: ingest mock data → compute risk → query API → assert correct metrics |
| Data validation | Manual | Compare computed VaR/volatility against Bloomberg or trusted tool for same basket/period |
| Frontend E2E | Playwright | View dashboard → change weights → verify recalculation → check alert triggers |
| ML validation | `pytest` | GARCH forecasts within reasonable bounds, HMM regime assignments stable |
| Smoke test | Docker Compose | `docker-compose up` → full stack starts → dashboard loads with real data |

---

## Risk & Mitigation

| Risk | Impact | Mitigation |
|------|--------|------------|
| yfinance rate limiting or breakage | Data pipeline stops | Store all historical data locally; retry with exponential backoff; have Polygon.io as fallback |
| yfinance data lag | Stale risk metrics | Validate data freshness; display "last updated" timestamp prominently; warn if data > 24h old |
| European ticker symbols wrong | Wrong data fetched | Verified: GLE.PA (Euronext Paris), SIE.DE (Frankfurt Xetra) |
| Market hour misalignment | Correlation on misaligned data | Align to daily close only; handle holidays where one market is open but another isn't |
| FX rate gaps (weekends/holidays) | Conversion fails | Forward-fill last known EUR/USD rate |
| VaR false confidence | Underestimates tail risk | Always show CVaR alongside VaR; include drawdown metrics; add regime context |
| Scope creep | Never ships | Phased approach; each phase is independently valuable and demoable |
