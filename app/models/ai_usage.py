"""AI usage tracking.

One row per Anthropic API call. Captures the four token buckets that
Anthropic bills against (`input_tokens` for uncached input,
`cache_creation_input_tokens` billed at ~1.25x, `cache_read_input_tokens`
billed at ~0.1x, `output_tokens`) and a derived USD cost, computed at
write time from the model's pricing.
"""

from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    Numeric,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AIUsage(Base):
    __tablename__ = "ai_usage"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True, index=True
    )
    job_id = Column(
        Integer, ForeignKey("ai_jobs.id", ondelete="SET NULL"), nullable=True
    )

    model = Column(String, nullable=False)

    input_tokens = Column(Integer, nullable=False, default=0)
    output_tokens = Column(Integer, nullable=False, default=0)
    cache_creation_input_tokens = Column(Integer, nullable=False, default=0)
    cache_read_input_tokens = Column(Integer, nullable=False, default=0)

    # USD; computed at insert from MODEL_PRICING.
    cost_usd = Column(Numeric(10, 6), nullable=False, default=0)

    stop_reason = Column(String, nullable=True)
    error = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False, index=True)

    organization = relationship("Organization")
    user = relationship("User")

    def __repr__(self):
        return (
            f"<AIUsage(id={self.id}, org={self.organization_id}, "
            f"model='{self.model}', in={self.input_tokens}, out={self.output_tokens}, "
            f"cost=${self.cost_usd})>"
        )
