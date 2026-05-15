"""
AI service.

Glue between the Anthropic client wrapper and the database — every call
goes through here so an `ai_usage` row is recorded for every Anthropic
invocation, billable or not. Higher layers (routes, the worker) call
this; nothing else touches `app.core.anthropic_client` directly.
"""

from __future__ import annotations

from decimal import Decimal
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from app.core.anthropic_client import (
    CompletionResult,
    TokenUsage,
    create_message,
    estimate_cost,
)
from app.core.config import settings
from app.models.ai_usage import AIUsage


class AIService:
    @staticmethod
    def complete(
        db: Session,
        *,
        organization_id: int,
        user_id: Optional[int],
        messages: List[Dict[str, Any]],
        system: Optional[str] = None,
        model: Optional[str] = None,
        max_tokens: Optional[int] = None,
        job_id: Optional[int] = None,
    ) -> CompletionResult:
        """
        Run a synchronous completion and record one ai_usage row.

        On API failure, still records a usage row with the error message
        and zero tokens so the audit trail covers attempted spend.
        """
        try:
            result = create_message(
                messages=messages,
                system=system,
                model=model,
                max_tokens=max_tokens,
            )
        except Exception as exc:
            AIService._record_failure(
                db,
                organization_id=organization_id,
                user_id=user_id,
                model=model or settings.ANTHROPIC_MODEL,
                job_id=job_id,
                error=str(exc),
            )
            raise

        db.add(
            AIUsage(
                organization_id=organization_id,
                user_id=user_id,
                job_id=job_id,
                model=result.model,
                input_tokens=result.usage.input_tokens,
                output_tokens=result.usage.output_tokens,
                cache_creation_input_tokens=result.usage.cache_creation_input_tokens,
                cache_read_input_tokens=result.usage.cache_read_input_tokens,
                cost_usd=result.cost_usd,
                stop_reason=result.stop_reason,
            )
        )
        db.commit()
        return result

    @staticmethod
    def _record_failure(
        db: Session,
        *,
        organization_id: int,
        user_id: Optional[int],
        model: str,
        job_id: Optional[int],
        error: str,
    ) -> None:
        try:
            db.add(
                AIUsage(
                    organization_id=organization_id,
                    user_id=user_id,
                    job_id=job_id,
                    model=model,
                    cost_usd=Decimal("0"),
                    error=error[:1000],
                )
            )
            db.commit()
        except Exception:
            db.rollback()  # never let usage-recording mask the original error

    @staticmethod
    def org_usage_totals(db: Session, organization_id: int) -> Dict[str, Any]:
        """Aggregate input/output/cost across all calls for an org. Cheap dashboard query."""
        from sqlalchemy import func

        row = (
            db.query(
                func.coalesce(func.sum(AIUsage.input_tokens), 0),
                func.coalesce(func.sum(AIUsage.output_tokens), 0),
                func.coalesce(func.sum(AIUsage.cache_read_input_tokens), 0),
                func.coalesce(func.sum(AIUsage.cost_usd), 0),
                func.count(AIUsage.id),
            )
            .filter(AIUsage.organization_id == organization_id)
            .one()
        )
        return {
            "calls": row[4],
            "input_tokens": row[0],
            "output_tokens": row[1],
            "cache_read_input_tokens": row[2],
            "cost_usd": str(row[3]),
        }
