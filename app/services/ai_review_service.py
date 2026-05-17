"""
AI weekly review generator.

Feeds the past 7 days of aggregates into Claude, stores the response
as an `ai_reviews` row, and records the usage row via AIService.

The prompt is shaped so the model:
- Cites specific customer names and dollar amounts (no vague "growth").
- Marks risks separately so the UI can highlight them.
- Stays under ~200 words.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Optional

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.ai_review import AIReview
from app.services.ai_service import AIService
from app.services.dashboard_service import DashboardService


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _format_money(cents: int) -> str:
    return f"${cents / 100:,.0f}"


def _format_pct(delta_pct: float) -> str:
    sign = "+" if delta_pct >= 0 else ""
    return f"{sign}{delta_pct:.1f}%"


SYSTEM_PROMPT = (
    "You are a confident, direct revenue analyst writing a weekly review "
    "of a B2B SaaS account. Your audience is the founder. Write three "
    "paragraphs, each 1-3 sentences:\n\n"
    "1. **Headline** — what happened this week. Lead with the most "
    "important number. State it plainly.\n"
    "2. **Bright spot** — one specific, named win (a particular customer, "
    "a specific product line, an actual dollar amount).\n"
    "3. **Watch** — one specific risk or trend worth attention this week, "
    "with the evidence right there.\n\n"
    "Cite real numbers and customer names from the data block. Do not "
    "invent. If there is no clear bright spot or watch item, say so "
    "rather than make one up. Stay under 200 words total. Skip the "
    "preamble — open with the headline."
)


class AIReviewService:
    @staticmethod
    def generate(
        db: Session,
        *,
        organization_id: int,
        user_id: Optional[int] = None,
        period_days: int = 7,
    ) -> AIReview:
        """Generate a new review and persist it.

        Idempotent in the sense that calling it twice produces two rows
        — the *latest* one is what `/ai/reviews/latest` returns. Older
        reviews stay around as the audit/history trail.
        """
        now = _utcnow()
        since = now - timedelta(days=period_days)

        overview = DashboardService.overview(db, organization_id)
        activity = DashboardService.recent_activity(db, organization_id, days=period_days)

        # MRR delta and pct for the prompt.
        mrr_delta = overview.mrr_cents - overview.mrr_cents_prev
        mrr_pct = (
            (mrr_delta / overview.mrr_cents_prev * 100)
            if overview.mrr_cents_prev > 0
            else 0.0
        )

        snapshot = {
            "period_start": since.isoformat(),
            "period_end": now.isoformat(),
            "mrr_cents": overview.mrr_cents,
            "mrr_cents_prev_30d": overview.mrr_cents_prev,
            "mrr_delta_cents": mrr_delta,
            "mrr_delta_pct": round(mrr_pct, 2),
            "arr_cents": overview.arr_cents,
            "active_customers": overview.active_customers,
            "active_customers_prev_30d": overview.active_customers_prev,
            "churn_rate_30d": round(overview.churn_rate, 4),
            "churn_rate_prev_30d": round(overview.churn_rate_prev, 4),
            "new_customers_in_window": activity["new_customers"],
            "churned_customers_in_window": activity["churned_customers"],
            "revenue_in_window_cents": activity["revenue_cents"],
            "top_new_customers": activity["top_new_customers"],
            "top_churned_customers": activity["top_churned_customers"],
        }

        # User message: the data block in compact JSON. Keep it deterministic
        # so prompt caching has a chance to hit on repeated regenerations
        # from the same week.
        data_block = json.dumps(snapshot, indent=2, sort_keys=True, default=str)
        user_message = (
            f"Here is the past {period_days} days for this account:\n\n"
            f"```json\n{data_block}\n```\n\n"
            f"Write the weekly review."
        )

        result = AIService.complete(
            db,
            organization_id=organization_id,
            user_id=user_id,
            messages=[{"role": "user", "content": user_message}],
            system=SYSTEM_PROMPT,
            max_tokens=800,
        )

        review = AIReview(
            organization_id=organization_id,
            period_start=since,
            period_end=now,
            model=result.model,
            content=result.text,
            metrics_snapshot=snapshot,
        )
        db.add(review)
        db.commit()
        db.refresh(review)
        return review

    @staticmethod
    def latest(db: Session, organization_id: int) -> Optional[AIReview]:
        return (
            db.query(AIReview)
            .filter(AIReview.organization_id == organization_id)
            .order_by(AIReview.created_at.desc())
            .first()
        )
