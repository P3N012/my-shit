"""
AI endpoints. All org-scoped via `X-Organization-Id` header.

  POST /ai/messages        — synchronous completion
  POST /ai/jobs            — enqueue an async completion via arq
  GET  /ai/jobs/{id}       — poll job status / fetch result
  GET  /ai/usage           — current org's cumulative token & cost totals
"""

import logging
from typing import Optional

from arq import create_pool
from arq.connections import RedisSettings
from fastapi import APIRouter, Body, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.core.limiter import limiter
from app.models.ai_job import AIJob
from app.models.organization import Membership
from app.schemas.ai import (
    JobCreatedResponse,
    JobStatusResponse,
    MessagesRequest,
    MessagesResponse,
    TokenUsageSchema,
    UsageSummaryResponse,
)
from app.services.ai_service import AIService
from app.services.jobs_service import JobsService
from app.utils.dependencies import get_current_membership

logger = logging.getLogger("api.ai")
router = APIRouter(prefix="/ai", tags=["AI"])


def _check_enabled() -> None:
    if not settings.AI_ENABLED:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI endpoints are disabled (set AI_ENABLED=true).",
        )


@router.post(
    "/messages",
    response_model=MessagesResponse,
    responses={429: {"description": "Rate limit exceeded"}, 503: {"description": "AI disabled"}},
)
@limiter.limit(settings.RATE_LIMIT_AI)
def create_message(
    request: Request,
    payload: MessagesRequest = Body(...),
    membership: Membership = Depends(get_current_membership),
    db: Session = Depends(get_db),
):
    """Synchronous completion. Records one ai_usage row before returning."""
    _check_enabled()
    try:
        result = AIService.complete(
            db,
            organization_id=membership.organization_id,
            user_id=membership.user_id,
            messages=[m.model_dump() for m in payload.messages],
            system=payload.system,
            model=payload.model,
            max_tokens=payload.max_tokens,
        )
    except RuntimeError as exc:
        # ANTHROPIC_API_KEY missing — surface as 503, don't leak the message
        logger.warning(f"AI not configured: {exc}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="AI is not configured on this server.",
        )
    except Exception as exc:
        logger.exception("AI call failed")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Upstream AI call failed: {exc}",
        )

    return MessagesResponse(
        text=result.text,
        model=result.model,
        stop_reason=result.stop_reason,
        usage=TokenUsageSchema(
            input_tokens=result.usage.input_tokens,
            output_tokens=result.usage.output_tokens,
            cache_creation_input_tokens=result.usage.cache_creation_input_tokens,
            cache_read_input_tokens=result.usage.cache_read_input_tokens,
        ),
        cost_usd=str(result.cost_usd),
    )


@router.post(
    "/jobs",
    response_model=JobCreatedResponse,
    status_code=status.HTTP_202_ACCEPTED,
)
@limiter.limit(settings.RATE_LIMIT_AI)
async def enqueue_job(
    request: Request,
    payload: MessagesRequest = Body(...),
    membership: Membership = Depends(get_current_membership),
    db: Session = Depends(get_db),
):
    """
    Async completion. Returns a job id immediately; the worker picks it
    up off Redis. Poll `GET /ai/jobs/{id}` for status and result.
    """
    _check_enabled()

    job = JobsService.create(
        db,
        organization_id=membership.organization_id,
        user_id=membership.user_id,
        kind="messages",
        request={
            "messages": [m.model_dump() for m in payload.messages],
            "system": payload.system,
            "model": payload.model,
            "max_tokens": payload.max_tokens,
        },
    )

    try:
        pool = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
        await pool.enqueue_job("run_messages_job", job.id)
        await pool.close()
    except Exception as exc:
        # Job row is persisted but never picked up — surface as 503 and
        # mark the job failed so the client doesn't poll forever.
        JobsService.mark_failed(db, job.id, f"failed to enqueue: {exc}")
        logger.exception("enqueue failed")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Job queue unavailable.",
        )

    return JobCreatedResponse(job_id=job.id, status=job.status)


@router.get(
    "/jobs/{job_id}",
    response_model=JobStatusResponse,
    responses={404: {"description": "Job not found in this org"}},
)
def get_job(
    job_id: int,
    membership: Membership = Depends(get_current_membership),
    db: Session = Depends(get_db),
):
    job: Optional[AIJob] = JobsService.get(
        db, job_id=job_id, organization_id=membership.organization_id
    )
    if job is None:
        raise HTTPException(status_code=404, detail="Job not found")
    return JobStatusResponse.model_validate(job)


@router.get("/usage", response_model=UsageSummaryResponse)
def get_usage(
    membership: Membership = Depends(get_current_membership),
    db: Session = Depends(get_db),
):
    totals = AIService.org_usage_totals(db, organization_id=membership.organization_id)
    return UsageSummaryResponse(**totals)
