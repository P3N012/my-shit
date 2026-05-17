"""
AI-generated weekly account review.

One row per generation, scoped to an organization. The `period_start`
and `period_end` bound the data window the review covers; `content` is
the rendered text Claude returned; `metrics_snapshot` captures the
aggregate values we sent to the model so the review can be re-rendered
or audited later without re-querying.
"""

from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AIReview(Base):
    __tablename__ = "ai_reviews"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(
        Integer,
        ForeignKey("organizations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )

    period_start = Column(DateTime(timezone=True), nullable=False)
    period_end = Column(DateTime(timezone=True), nullable=False, index=True)

    model = Column(String, nullable=False)
    content = Column(Text, nullable=False)
    metrics_snapshot = Column(JSON, nullable=True)

    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False, index=True)

    organization = relationship("Organization")
