"""OHLCV daily price model — TimescaleDB hypertable."""

from sqlalchemy import Column, String, Float, BigInteger, DateTime, Index
from app.database import Base


class OHLCVDaily(Base):
    __tablename__ = "ohlcv_daily"

    time = Column(DateTime(timezone=True), primary_key=True, nullable=False)
    ticker = Column(String, primary_key=True, nullable=False)
    open = Column(Float)
    high = Column(Float)
    low = Column(Float)
    close = Column(Float)
    adj_close = Column(Float)
    volume = Column(BigInteger)
    currency = Column(String, nullable=False)

    __table_args__ = (
        Index("ix_ohlcv_ticker_time", "ticker", "time"),
    )

    def __repr__(self) -> str:
        return f"<OHLCV {self.ticker} {self.time} close={self.close}>"
