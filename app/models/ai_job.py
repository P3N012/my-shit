"""Background AI job.

Long-running Anthropic calls are enqueued through arq; this row tracks
their lifecycle so a client can poll `GET /ai/jobs/{id}` for status.
The job's `request` (the messages payload) and eventual `result` (the
assistant's text response) are stored as JSON. Errors land in `error`.
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


# Job lifecycle. Add new states at the end for forward compatibility.
JOB_QUEUED = "queued"
JOB_RUNNING = "running"
JOB_SUCCEEDED = "succeeded"
JOB_FAILED = "failed"
JOB_TERMINAL = (JOB_SUCCEEDED, JOB_FAILED)


class AIJob(Base):
    __tablename__ = "ai_jobs"

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    kind = Column(String, nullable=False)  # e.g. "messages"
    status = Column(String, nullable=False, default=JOB_QUEUED, index=True)

    request = Column(JSON, nullable=False)
    result = Column(JSON, nullable=True)
    error = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False, index=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    finished_at = Column(DateTime(timezone=True), nullable=True)

    organization = relationship("Organization")
    user = relationship("User")

    def __repr__(self):
        return f"<AIJob(id={self.id}, kind='{self.kind}', status='{self.status}')>"
