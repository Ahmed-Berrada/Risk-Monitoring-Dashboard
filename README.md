# Risk Monitoring Dashboard

A full-stack **portfolio risk monitoring dashboard** for a basket of 3 assets — S&P 500, Société Générale, and Siemens — with real-time risk metrics, ML-driven insights, alerting, and stress testing.

Built as a **hybrid modular monolith** with event-driven internals, designed to demonstrate industry-standard risk management practices.

![Python](https://img.shields.io/badge/Python-3.12-blue) ![FastAPI](https://img.shields.io/badge/FastAPI-0.135-009688) ![Next.js](https://img.shields.io/badge/Next.js-14-black) ![TimescaleDB](https://img.shields.io/badge/TimescaleDB-PG16-FDB515) ![License](https://img.shields.io/badge/License-MIT-green)

---

## Features

### Risk Engine
- **Value-at-Risk** (95% & 99%) — historical simulation method
- **Conditional VaR** (Expected Shortfall) — tail risk measure
- **Rolling volatility** (21-day & 63-day annualised)
- **Maximum & current drawdown** tracking
- **Sharpe & Sortino ratios** — risk-adjusted performance
- **Beta** relative to S&P 500
- **Correlation matrix** (63-day rolling)
- **Risk contribution** per asset — marginal risk decomposition
- **Tracking error** vs benchmark

### AI/ML Layer
- **GARCH(1,1)** volatility forecasting per asset (Student-t distribution)
- **Hidden Markov Model** (3-state) regime detection — Calm / Normal / Stressed
- **Isolation Forest** anomaly detection — per-asset + cross-asset joint analysis

### Alerting & Decision Support
- **Rule-based alerting** with configurable thresholds (warning / breach)
- **10 default rules** covering VaR, drawdown, volatility, Sharpe thresholds
- **SSE (Server-Sent Events)** real-time push to frontend
- **Historical stress testing** — 4 pre-defined crisis scenarios (2008 GFC, 2011 EU Debt, 2020 COVID, 2022 Rate Hikes)
- **Custom stress scenarios** with user-defined shocks

### Data Pipeline
- **5 years** of daily OHLCV data via yfinance
- **Automatic EUR conversion** of USD-denominated assets (S&P 500)
- **Data quality guards** — null/zero checks, large move detection (>20%)
- **Event-driven recomputation** — data refresh triggers risk → ML → alerts cascade

---

## Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                        Next.js Frontend                        │
│  KPI Cards │ Charts (Recharts) │ ML Panels │ Alert & Stress    │
│                    SWR auto-refresh (60s)                      │
└────────────────────────┬───────────────────────────────────────┘
                         │ REST API + SSE
┌────────────────────────┴───────────────────────────────────────┐
│                    FastAPI Backend (Modular Monolith)           │
│                                                                │
│  ┌──────────┐  ┌────────────┐  ┌────────┐  ┌───────────────┐  │
│  │ Ingestion│  │ Risk Engine│  │   ML   │  │   Alerting    │  │
│  │ Service  │  │  Service   │  │Service │  │   Service     │  │
│  └────┬─────┘  └─────┬──────┘  └───┬────┘  └───────┬───────┘  │
│       │              │             │               │           │
│       └──────────────┴─────────────┴───────────────┘           │
│              PostgreSQL LISTEN/NOTIFY Event Bus                │
│                                                                │
│  ┌───────────┐  ┌────────────┐  ┌──────────────────────────┐  │
│  │    FX     │  │ Portfolio  │  │    Stress Testing        │  │
│  │  Service  │  │  Service   │  │       Engine             │  │
│  └───────────┘  └────────────┘  └──────────────────────────┘  │
└────────────────────────┬───────────────────────────────────────┘
                         │
          ┌──────────────┴──────────────┐
          │                             │
  ┌───────┴────────┐          ┌────────┴────────┐
  │  TimescaleDB   │          │     Redis       │
  │  (PostgreSQL)  │          │   (Cache)       │
  │  5 hypertables │          │                 │
  └────────────────┘          └─────────────────┘
```

### Event Flow

```
yfinance → Ingestion Service
    ↓ (data_refreshed)
Risk Engine → compute 52 metrics
    ↓ (risk_updated)
├── ML Service → GARCH + HMM + Anomaly Detection
├── Alert Service → evaluate rules → log events
└── SSE Broadcast → push to frontend
```

---

## Tech Stack

| Layer | Technology | Purpose |
|-------|-----------|---------|
| **Frontend** | Next.js 14, TypeScript, Tailwind CSS, Recharts, SWR | Dashboard UI with auto-refresh |
| **Backend** | FastAPI, SQLAlchemy (async), asyncpg, Pydantic | REST API + event bus |
| **Database** | TimescaleDB (PostgreSQL 16) | Time-series storage with hypertables |
| **Cache** | Redis 7 | Metric caching |
| **ML** | arch (GARCH), hmmlearn (HMM), scikit-learn (Isolation Forest) | Volatility forecasting, regime detection, anomaly detection |
| **Data** | yfinance | Market data (OHLCV + FX rates) |
| **Infra** | Docker Compose | Full-stack deployment |

---

## Quick Start

### Prerequisites
- Docker & Docker Compose
- Git

### One-command deployment

```bash
git clone <repo-url>
cd Risk-Monitoring-Dashboard

# Start everything
docker compose up -d

# Wait for DB to be ready, then backfill data
docker compose exec backend python -m app.cli backfill

# Compute risk metrics
curl -X POST http://localhost:8000/api/risk/compute

# Seed alert rules
curl -X POST http://localhost:8000/api/alerts/seed
```

Dashboard: **http://localhost:3000**
API docs: **http://localhost:8000/docs**

### Local Development

```bash
# 1. Start infrastructure
docker compose up -d db redis

# 2. Backend
cd backend
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
uvicorn app.main:app --reload --port 8000

# 3. Frontend (new terminal)
cd frontend
npm install
npm run dev
```

---

## API Reference

### Risk Metrics
| Method | Endpoint | Description |
|--------|----------|-------------|
| `POST` | `/api/risk/compute` | Trigger risk metric computation |
| `GET` | `/api/risk/summary` | Latest metrics for all assets + portfolio |
| `GET` | `/api/risk/history?metric=var_95&ticker=PORTFOLIO&days=252` | Historical metric series |
| `GET` | `/api/risk/correlation` | 3×3 correlation matrix |
| `GET` | `/api/risk/contribution` | Per-asset risk contribution |
| `GET` | `/api/risk/series` | Rolling time series for charting |

### Portfolio
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/portfolio` | Current weights |
| `PUT` | `/api/portfolio/weights` | Update weights (triggers recomputation) |

### ML / AI
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/ml/garch` | GARCH(1,1) volatility forecasts per asset |
| `GET` | `/api/ml/regimes` | HMM regime detection (Calm/Normal/Stressed) |
| `GET` | `/api/ml/anomalies` | Isolation Forest anomaly detection |
| `POST` | `/api/ml/compute` | Trigger all ML model recomputation |

### Alerting
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/alerts/rules` | List active alert rules |
| `POST` | `/api/alerts/rules` | Create new rule |
| `PUT` | `/api/alerts/rules/{id}` | Update rule |
| `DELETE` | `/api/alerts/rules/{id}` | Delete rule |
| `POST` | `/api/alerts/evaluate` | Evaluate all rules now |
| `GET` | `/api/alerts/events` | Recent alert history |

### Stress Testing
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/stress/scenarios` | List available scenarios |
| `GET` | `/api/stress/run/{id}` | Run a specific scenario |
| `GET` | `/api/stress/run-all` | Run all scenarios |
| `POST` | `/api/stress/run/custom` | Custom shock scenario |

### Real-time
| Method | Endpoint | Description |
|--------|----------|-------------|
| `GET` | `/api/stream` | SSE stream (risk_updated, alert_triggered) |

---

## Dashboard Layout

| Row | Components |
|-----|-----------|
| **Header** | Portfolio name, regime badge, anomaly alert, alert count, data freshness |
| **Row 1** | 6 KPI cards — VaR 95%, VaR 99%, CVaR, Drawdown, Volatility, Sharpe |
| **Row 2** | Rolling volatility chart (21d/63d toggle) + Portfolio weights panel |
| **Row 3** | Drawdown chart + Correlation heatmap + Risk contribution bars |
| **Row 4** | GARCH forecast chart + Regime panel + Anomaly panel |
| **Row 5** | Alert monitor + Stress testing comparison panel |
| **Row 6** | Expandable detailed metrics table (10 metrics × 4 columns) |

---

## Database Schema

5 hypertables + 1 regular table in TimescaleDB:

| Table | Type | Purpose |
|-------|------|---------|
| `ohlcv_daily` | Hypertable | Daily price data (OHLCV) |
| `fx_rates` | Hypertable | EUR/USD exchange rates |
| `risk_metrics` | Hypertable | Computed risk metrics |
| `alert_events` | Hypertable | Alert event history |
| `portfolio_weights` | Regular | Portfolio weight snapshots |
| `alert_rules` | Regular | Alert rule definitions |

---

## Project Structure

```
Risk-Monitoring-Dashboard/
├── backend/
│   ├── app/
│   │   ├── api/                  # FastAPI routers
│   │   │   ├── health.py
│   │   │   ├── ingestion.py
│   │   │   ├── risk.py
│   │   │   ├── portfolio.py
│   │   │   ├── ml.py
│   │   │   ├── alerts.py
│   │   │   ├── stress.py
│   │   │   └── stream.py        # SSE endpoint
│   │   ├── models/               # SQLAlchemy models
│   │   ├── services/
│   │   │   ├── ingestion/        # yfinance data fetcher
│   │   │   ├── fx/               # EUR/USD conversion
│   │   │   ├── risk_engine/      # Risk metrics + orchestrator
│   │   │   ├── ml/               # GARCH, HMM, anomaly detection
│   │   │   ├── alerting/         # Rule evaluation + event logging
│   │   │   ├── stress_test/      # Historical scenario replay
│   │   │   └── portfolio/        # Weight management
│   │   ├── config.py             # Pydantic settings
│   │   ├── database.py           # Async SQLAlchemy engine
│   │   ├── events.py             # PostgreSQL LISTEN/NOTIFY bus
│   │   ├── main.py               # App factory + lifespan
│   │   └── cli.py                # Click CLI (backfill, ingest)
│   ├── Dockerfile
│   ├── requirements.txt
│   └── .env.example
├── frontend/
│   ├── src/
│   │   ├── app/page.tsx          # Main dashboard
│   │   ├── components/           # 11 React components
│   │   └── lib/                  # API client, hooks, types
│   ├── Dockerfile
│   └── package.json
├── db/
│   └── init.sql                  # Schema + hypertables
├── docker-compose.yml            # Full-stack deployment
└── README.md
```

---

## Assets

| Asset | Ticker | Exchange | Currency | Notes |
|-------|--------|----------|----------|-------|
| S&P 500 | `^GSPC` | NYSE | USD → EUR | Converted via EUR/USD rate |
| Société Générale | `GLE.PA` | Euronext Paris | EUR | Native EUR |
| Siemens | `SIE.DE` | Frankfurt (Xetra) | EUR | Native EUR |

---

## Risk Metrics Computed

| # | Metric | Per-Asset | Portfolio | Window |
|---|--------|-----------|-----------|--------|
| 1 | VaR 95% | ✅ | ✅ | 252d |
| 2 | VaR 99% | ✅ | ✅ | 252d |
| 3 | CVaR 95% | ✅ | ✅ | 252d |
| 4 | CVaR 99% | ✅ | ✅ | 252d |
| 5 | Volatility 21d | ✅ | ✅ | 21d |
| 6 | Volatility 63d | ✅ | ✅ | 63d |
| 7 | Max Drawdown | ✅ | ✅ | Full |
| 8 | Current Drawdown | ✅ | ✅ | Full |
| 9 | Sharpe Ratio | ✅ | ✅ | 252d |
| 10 | Sortino Ratio | ✅ | ✅ | 252d |
| 11 | Beta | ✅ | — | 252d |
| 12 | Tracking Error | — | ✅ | 252d |
| 13 | Risk Contribution | ✅ | — | 252d |
| 14 | Correlation (63d) | pairwise | — | 63d |

---

## ML Models

| Model | Library | What It Does | Key Output |
|-------|---------|-------------|------------|
| **GARCH(1,1)** | `arch` | Volatility forecasting with Student-t errors | 10-day annualised vol forecast, α/β/persistence params |
| **Gaussian HMM** | `hmmlearn` | 3-state regime detection via Viterbi decoding | Current regime (Calm/Normal/Stressed), transition matrix |
| **Isolation Forest** | `scikit-learn` | Anomaly detection on 5 return features | Anomaly scores, severity classification, recent events |

---

## License

MIT
