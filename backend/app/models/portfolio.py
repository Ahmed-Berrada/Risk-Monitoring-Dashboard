"""Portfolio weight model."""

from sqlalchemy import Column, Integer, Boolean, DateTime, func
from sqlalchemy.dialects.postgresql import JSONB
from app.database import Base


class PortfolioWeight(Base):
    __tablename__ = "portfolio_weights"

    id = Column(Integer, primary_key=True, autoincrement=True)
    weights = Column(JSONB, nullable=False)  # {"^GSPC": 0.33, "GLE.PA": 0.33, "SIE.DE": 0.34}
    created_at = Column(DateTime(timezone=True), server_default=func.now())
    is_active = Column(Boolean, default=True)

    def __repr__(self) -> str:
        return f"<PortfolioWeight active={self.is_active} weights={self.weights}>"
