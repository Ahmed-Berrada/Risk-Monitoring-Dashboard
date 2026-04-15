"""Risk metric model — TimescaleDB hypertable."""

from sqlalchemy import Column, String, Float, Integer, DateTime, Index
from sqlalchemy.dialects.postgresql import JSONB
from app.database import Base


class RiskMetric(Base):
    __tablename__ = "risk_metrics"

    time = Column(DateTime(timezone=True), primary_key=True, nullable=False)
    ticker = Column(String, primary_key=True, nullable=True)  # NULL = portfolio-level
    metric_name = Column(String, primary_key=True, nullable=False)
    value = Column(Float, nullable=False)
    window_days = Column(Integer)
    weights = Column(JSONB)  # portfolio weights snapshot

    __table_args__ = (
        Index("ix_risk_metric_ticker_name_time", "ticker", "metric_name", "time"),
    )

    def __repr__(self) -> str:
        target = self.ticker or "PORTFOLIO"
        return f"<RiskMetric {target} {self.metric_name}={self.value:.4f}>"
