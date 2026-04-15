"""FX rate model — TimescaleDB hypertable."""

from sqlalchemy import Column, String, Float, DateTime, Index
from app.database import Base


class FXRate(Base):
    __tablename__ = "fx_rates"

    time = Column(DateTime(timezone=True), primary_key=True, nullable=False)
    pair = Column(String, primary_key=True, nullable=False)  # e.g. 'EURUSD'
    rate = Column(Float, nullable=False)

    __table_args__ = (
        Index("ix_fx_pair_time", "pair", "time"),
    )

    def __repr__(self) -> str:
        return f"<FXRate {self.pair} {self.time} rate={self.rate}>"
