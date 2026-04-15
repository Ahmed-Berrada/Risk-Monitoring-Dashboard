-- Enable TimescaleDB extension
CREATE EXTENSION IF NOT EXISTS timescaledb;

-- ── OHLCV Daily Prices ──────────────────────────────────────────
CREATE TABLE IF NOT EXISTS ohlcv_daily (
    time        TIMESTAMPTZ NOT NULL,
    ticker      TEXT NOT NULL,
    open        DOUBLE PRECISION,
    high        DOUBLE PRECISION,
    low         DOUBLE PRECISION,
    close       DOUBLE PRECISION,
    adj_close   DOUBLE PRECISION,
    volume      BIGINT,
    currency    TEXT NOT NULL,
    PRIMARY KEY (time, ticker)
);
SELECT create_hypertable('ohlcv_daily', 'time', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS ix_ohlcv_ticker_time ON ohlcv_daily (ticker, time DESC);

-- ── FX Rates ────────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS fx_rates (
    time        TIMESTAMPTZ NOT NULL,
    pair        TEXT NOT NULL,
    rate        DOUBLE PRECISION NOT NULL,
    PRIMARY KEY (time, pair)
);
SELECT create_hypertable('fx_rates', 'time', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS ix_fx_pair_time ON fx_rates (pair, time DESC);

-- ── Risk Metrics ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS risk_metrics (
    time         TIMESTAMPTZ NOT NULL,
    ticker       TEXT,
    metric_name  TEXT NOT NULL,
    value        DOUBLE PRECISION NOT NULL,
    window_days  INT,
    weights      JSONB,
    PRIMARY KEY (time, ticker, metric_name)
);
SELECT create_hypertable('risk_metrics', 'time', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS ix_risk_metric_ticker_name_time
    ON risk_metrics (ticker, metric_name, time DESC);

-- ── Portfolio Weights ───────────────────────────────────────────
CREATE TABLE IF NOT EXISTS portfolio_weights (
    id          SERIAL PRIMARY KEY,
    weights     JSONB NOT NULL,
    created_at  TIMESTAMPTZ DEFAULT NOW(),
    is_active   BOOLEAN DEFAULT TRUE
);

-- Insert default equal weights
INSERT INTO portfolio_weights (weights, is_active)
VALUES ('{"^GSPC": 0.3333, "GLE.PA": 0.3333, "SIE.DE": 0.3334}'::jsonb, true);

-- ── Alert Rules ─────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS alert_rules (
    id          SERIAL PRIMARY KEY,
    metric_name TEXT NOT NULL,
    ticker      TEXT,
    operator    TEXT NOT NULL,
    threshold   DOUBLE PRECISION NOT NULL,
    severity    TEXT NOT NULL,
    is_active   BOOLEAN DEFAULT TRUE
);

-- ── Alert Events ────────────────────────────────────────────────
CREATE TABLE IF NOT EXISTS alert_events (
    time         TIMESTAMPTZ NOT NULL,
    rule_id      INT REFERENCES alert_rules(id),
    metric_value DOUBLE PRECISION,
    message      TEXT,
    PRIMARY KEY (time, rule_id)
);
SELECT create_hypertable('alert_events', 'time', if_not_exists => TRUE);
CREATE INDEX IF NOT EXISTS ix_alert_events_rule_time
    ON alert_events (rule_id, time DESC);
