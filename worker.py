"""
arq worker entry point.

Run with:
    arq worker.WorkerSettings

Background tasks live here. Each task takes the job id as its first
arg, loads the job from Postgres, runs the work, writes the result
back, and records ai_usage along the way (via AIService).
"""

from __future__ import annotations

from typing import Any, Dict

from arq.connections import RedisSettings

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.logging import configure_logging
from app.services.ai_service import AIService
from app.services.jobs_service import JobsService


async def run_messages_job(ctx, job_id: int) -> Dict[str, Any]:
    """
    Execute a queued `messages`-kind AI job.

    The arq runtime calls this with a context dict (first arg) and the
    job id we enqueued. We do everything in a fresh SQLAlchemy session
    — workers are long-running, so don't hold a session across tasks.
    """
    db = SessionLocal()
    try:
        job = db.query(__import__("app.models.ai_job", fromlist=["AIJob"]).AIJob).get(job_id)
        if job is None:
            return {"error": f"job {job_id} not found"}

        JobsService.mark_running(db, job_id)
        request = job.request or {}

        try:
            result = AIService.complete(
                db,
                organization_id=job.organization_id,
                user_id=job.user_id,
                messages=request.get("messages", []),
                system=request.get("system"),
                model=request.get("model"),
                max_tokens=request.get("max_tokens"),
                job_id=job_id,
            )
        except Exception as exc:
            JobsService.mark_failed(db, job_id, str(exc))
            return {"status": "failed", "error": str(exc)}

        payload = {
            "text": result.text,
            "model": result.model,
            "stop_reason": result.stop_reason,
            "usage": {
                "input_tokens": result.usage.input_tokens,
                "output_tokens": result.usage.output_tokens,
                "cache_creation_input_tokens": result.usage.cache_creation_input_tokens,
                "cache_read_input_tokens": result.usage.cache_read_input_tokens,
            },
            "cost_usd": str(result.cost_usd),
        }
        JobsService.mark_succeeded(db, job_id, payload)
        return {"status": "succeeded", "job_id": job_id}
    finally:
        db.close()


async def startup(ctx) -> None:
    configure_logging(level=settings.LOG_LEVEL, environment=settings.ENVIRONMENT)


class WorkerSettings:
    """arq worker configuration."""
    functions = [run_messages_job]
    on_startup = startup
    redis_settings = RedisSettings.from_dsn(settings.REDIS_URL)
    max_jobs = 10
    job_timeout = 600  # 10 minutes — Anthropic calls can be long under load
