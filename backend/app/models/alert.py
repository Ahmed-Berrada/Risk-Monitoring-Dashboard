"""Alert rule and event models."""

from sqlalchemy import Column, Integer, String, Float, Boolean, DateTime, ForeignKey, func, Index
from app.database import Base


class AlertRule(Base):
    __tablename__ = "alert_rules"

    id = Column(Integer, primary_key=True, autoincrement=True)
    metric_name = Column(String, nullable=False)
    ticker = Column(String, nullable=True)  # NULL = portfolio-level
    operator = Column(String, nullable=False)  # 'gt', 'lt', 'gte', 'lte'
    threshold = Column(Float, nullable=False)
    severity = Column(String, nullable=False)  # 'warning', 'breach'
    is_active = Column(Boolean, default=True)

    def __repr__(self) -> str:
        target = self.ticker or "PORTFOLIO"
        return f"<AlertRule {target} {self.metric_name} {self.operator} {self.threshold}>"


class AlertEvent(Base):
    __tablename__ = "alert_events"

    time = Column(DateTime(timezone=True), primary_key=True, nullable=False)
    rule_id = Column(Integer, ForeignKey("alert_rules.id"), primary_key=True)
    metric_value = Column(Float)
    message = Column(String)

    __table_args__ = (
        Index("ix_alert_events_rule_time", "rule_id", "time"),
    )

    def __repr__(self) -> str:
        return f"<AlertEvent rule={self.rule_id} value={self.metric_value}>"
