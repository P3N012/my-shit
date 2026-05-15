"""CRUD for AI jobs."""

from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy.orm import Session

from app.models.ai_job import (
    JOB_FAILED,
    JOB_QUEUED,
    JOB_RUNNING,
    JOB_SUCCEEDED,
    AIJob,
)


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class JobsService:
    @staticmethod
    def create(
        db: Session,
        *,
        organization_id: int,
        user_id: int,
        kind: str,
        request: Dict[str, Any],
    ) -> AIJob:
        job = AIJob(
            organization_id=organization_id,
            user_id=user_id,
            kind=kind,
            status=JOB_QUEUED,
            request=request,
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        return job

    @staticmethod
    def get(db: Session, job_id: int, organization_id: int) -> Optional[AIJob]:
        return (
            db.query(AIJob)
            .filter(AIJob.id == job_id, AIJob.organization_id == organization_id)
            .first()
        )

    @staticmethod
    def mark_running(db: Session, job_id: int) -> None:
        db.query(AIJob).filter(AIJob.id == job_id).update(
            {"status": JOB_RUNNING, "started_at": _utcnow()}
        )
        db.commit()

    @staticmethod
    def mark_succeeded(db: Session, job_id: int, result: Dict[str, Any]) -> None:
        db.query(AIJob).filter(AIJob.id == job_id).update(
            {"status": JOB_SUCCEEDED, "result": result, "finished_at": _utcnow()}
        )
        db.commit()

    @staticmethod
    def mark_failed(db: Session, job_id: int, error: str) -> None:
        db.query(AIJob).filter(AIJob.id == job_id).update(
            {"status": JOB_FAILED, "error": error[:5000], "finished_at": _utcnow()}
        )
        db.commit()
