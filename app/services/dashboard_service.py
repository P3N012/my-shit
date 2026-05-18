"""
Dashboard aggregates.

Everything here is computed in Python from the mirrored Stripe tables —
no Stripe API calls at read time. The functions are pure: pass an org
id and a `db` session, get back numbers.

All money values stay in cents.

`normalize_to_monthly_cents` is the key building block: takes a
subscription with any Stripe interval (day / week / month / year) and
returns its monthly equivalent so we can sum MRR uniformly.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from typing import List, Optional

from dateutil.relativedelta import relativedelta
from sqlalchemy import and_, desc, func, or_
from sqlalchemy.orm import Session

from app.models.platform_connection import PlatformConnection
from app.models.stripe_data import StripeCharge, StripeCustomer, StripeSubscription


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# ---------------------------------------------------------------------------
# Unit conversion
# ---------------------------------------------------------------------------

_INTERVAL_PER_MONTH = {
    "day": 365 / 12,
    "week": 52 / 12,
    "month": 1.0,
    "year": 1 / 12,
}


def normalize_to_monthly_cents(amount_per_period: int, interval: Optional[str], interval_count: int) -> int:
    """Project a single period's amount to its monthly equivalent.

    Returns 0 if the interval is unknown (one-time / setup charge) or
    if interval_count is non-positive.
    """
    if not interval or interval_count <= 0:
        return 0
    factor = _INTERVAL_PER_MONTH.get(interval)
    if factor is None:
        return 0
    per_period = amount_per_period / interval_count
    return int(per_period * factor)


# ---------------------------------------------------------------------------
# Result shapes
# ---------------------------------------------------------------------------

@dataclass
class OverviewKpi:
    label: str
    value: str           # human-formatted, e.g. "$24,128" or "147"
    raw: float           # underlying number for charts/tests
    delta: Optional[str] # e.g. "+12.3%" or None when there's no comparison
    delta_positive: Optional[bool]


@dataclass
class Overview:
    mrr_cents: int
    arr_cents: int
    active_customers: int
    churn_rate: float    # 0..1
    mrr_cents_prev: int  # 30 days ago
    active_customers_prev: int
    churn_rate_prev: float
    failed_payments_count: int
    failed_payments_cents: int
    period_days: int


@dataclass
class TrendPoint:
    date: datetime
    mrr_cents: int


@dataclass
class MovementPoint:
    """Per-month MRR delta, decomposed into new vs. churned.

    With our current schema we can't reliably attribute expansion or
    contraction — that needs a subscription-changes history table. So
    we limit movements to the two we *can* compute from snapshot data:
    started-in-month and canceled-in-month.
    """
    month_start: datetime
    new_mrr_cents: int
    churn_mrr_cents: int   # positive number; the chart renders it as negative


@dataclass
class TopCustomer:
    stripe_customer_id: str
    name: Optional[str]
    email: Optional[str]
    total_revenue_cents: int


@dataclass
class ActivityEvent:
    kind: str            # "subscription_started" | "subscription_canceled" | "charge_failed"
    timestamp: datetime
    customer_name: Optional[str]
    customer_email: Optional[str]
    amount_cents: int    # MRR for subs, charge amount for charges
    description: str


# ---------------------------------------------------------------------------
# Service
# ---------------------------------------------------------------------------

class DashboardService:
    """Pure read-side aggregates over the mirrored Stripe tables."""

    # ---- helpers ----------------------------------------------------------

    @staticmethod
    def _connection_ids(db: Session, organization_id: int) -> List[int]:
        return [
            row[0]
            for row in db.query(PlatformConnection.id)
            .filter(PlatformConnection.organization_id == organization_id)
            .all()
        ]

    @staticmethod
    def _mrr_at(db: Session, connection_ids: List[int], at: datetime) -> int:
        """Point-in-time MRR: subscriptions active at `at`, summed and normalized."""
        if not connection_ids:
            return 0
        rows = (
            db.query(
                StripeSubscription.amount_per_period,
                StripeSubscription.interval,
                StripeSubscription.interval_count,
            )
            .filter(
                StripeSubscription.connection_id.in_(connection_ids),
                # Started on or before `at` — use stripe_created_at as the floor
                # so trial/incomplete subs don't get double-counted.
                StripeSubscription.stripe_created_at <= at,
                # Still active at `at`: not canceled, or canceled after `at`.
                or_(
                    StripeSubscription.canceled_at.is_(None),
                    StripeSubscription.canceled_at > at,
                ),
                StripeSubscription.status.in_(("active", "trialing", "past_due")),
            )
            .all()
        )
        return sum(
            normalize_to_monthly_cents(amt or 0, interval, count or 1)
            for (amt, interval, count) in rows
        )

    # ---- top-level views --------------------------------------------------

    @staticmethod
    def overview(db: Session, organization_id: int) -> Overview:
        connection_ids = DashboardService._connection_ids(db, organization_id)
        now = _utcnow()
        period_days = 30
        prev = now - timedelta(days=period_days)

        mrr_now = DashboardService._mrr_at(db, connection_ids, now)
        mrr_prev = DashboardService._mrr_at(db, connection_ids, prev)
        arr_now = mrr_now * 12

        if not connection_ids:
            return Overview(0, 0, 0, 0.0, 0, 0, 0.0, 0, 0, period_days)

        # Active customer counts at `now` and at `prev`.
        active_now = (
            db.query(func.count(func.distinct(StripeSubscription.stripe_customer_id)))
            .filter(
                StripeSubscription.connection_id.in_(connection_ids),
                StripeSubscription.status.in_(("active", "trialing", "past_due")),
                or_(
                    StripeSubscription.canceled_at.is_(None),
                    StripeSubscription.canceled_at > now,
                ),
            )
            .scalar()
            or 0
        )
        active_prev = (
            db.query(func.count(func.distinct(StripeSubscription.stripe_customer_id)))
            .filter(
                StripeSubscription.connection_id.in_(connection_ids),
                StripeSubscription.stripe_created_at <= prev,
                or_(
                    StripeSubscription.canceled_at.is_(None),
                    StripeSubscription.canceled_at > prev,
                ),
            )
            .scalar()
            or 0
        )

        # Churn rate over the last `period_days`: canceled in window / active at window start.
        canceled_in_window = (
            db.query(func.count(StripeSubscription.id))
            .filter(
                StripeSubscription.connection_id.in_(connection_ids),
                StripeSubscription.canceled_at >= prev,
                StripeSubscription.canceled_at <= now,
            )
            .scalar()
            or 0
        )
        churn = (canceled_in_window / active_prev) if active_prev > 0 else 0.0

        # For the "previous period" churn (used for the delta on the KPI card),
        # measure cancellations in the window BEFORE `prev`.
        prev_window_start = prev - timedelta(days=period_days)
        active_two_periods_ago = (
            db.query(func.count(func.distinct(StripeSubscription.stripe_customer_id)))
            .filter(
                StripeSubscription.connection_id.in_(connection_ids),
                StripeSubscription.stripe_created_at <= prev_window_start,
                or_(
                    StripeSubscription.canceled_at.is_(None),
                    StripeSubscription.canceled_at > prev_window_start,
                ),
            )
            .scalar()
            or 0
        )
        canceled_in_prev_window = (
            db.query(func.count(StripeSubscription.id))
            .filter(
                StripeSubscription.connection_id.in_(connection_ids),
                StripeSubscription.canceled_at >= prev_window_start,
                StripeSubscription.canceled_at < prev,
            )
            .scalar()
            or 0
        )
        churn_prev = (
            canceled_in_prev_window / active_two_periods_ago
            if active_two_periods_ago > 0
            else 0.0
        )

        # Failed-payment summary for the same 30-day window. Cheap to
        # compute alongside the rest so we don't have to fetch it as a
        # separate call from the frontend.
        failed_row = (
            db.query(
                func.count(StripeCharge.id),
                func.coalesce(func.sum(StripeCharge.amount), 0),
            )
            .filter(
                StripeCharge.connection_id.in_(connection_ids),
                StripeCharge.status == "failed",
                StripeCharge.stripe_created_at >= prev,
                StripeCharge.stripe_created_at <= now,
            )
            .one()
        )
        failed_count = int(failed_row[0] or 0)
        failed_amount_cents = int(failed_row[1] or 0)

        return Overview(
            mrr_cents=mrr_now,
            arr_cents=arr_now,
            active_customers=active_now,
            churn_rate=churn,
            mrr_cents_prev=mrr_prev,
            active_customers_prev=active_prev,
            churn_rate_prev=churn_prev,
            failed_payments_count=failed_count,
            failed_payments_cents=failed_amount_cents,
            period_days=period_days,
        )

    @staticmethod
    def mrr_movements(
        db: Session, organization_id: int, months: int = 12
    ) -> List[MovementPoint]:
        """Per-month decomposition of MRR change into new vs. churn.

        We can't compute expansion / contraction / reactivation from
        snapshot data — those need a subscription-change history. New
        and churn are derivable directly from
        `stripe_created_at` / `canceled_at` on the subscription rows.
        """
        connection_ids = DashboardService._connection_ids(db, organization_id)
        if not connection_ids:
            return []

        now = _utcnow()
        current_month_start = now.replace(
            day=1, hour=0, minute=0, second=0, microsecond=0
        )

        points: List[MovementPoint] = []
        for i in range(months - 1, -1, -1):
            month_start = current_month_start - relativedelta(months=i)
            month_end = month_start + relativedelta(months=1)

            new_rows = (
                db.query(
                    StripeSubscription.amount_per_period,
                    StripeSubscription.interval,
                    StripeSubscription.interval_count,
                )
                .filter(
                    StripeSubscription.connection_id.in_(connection_ids),
                    StripeSubscription.stripe_created_at >= month_start,
                    StripeSubscription.stripe_created_at < month_end,
                )
                .all()
            )
            new_mrr = sum(
                normalize_to_monthly_cents(amt or 0, interval, count or 1)
                for (amt, interval, count) in new_rows
            )

            churn_rows = (
                db.query(
                    StripeSubscription.amount_per_period,
                    StripeSubscription.interval,
                    StripeSubscription.interval_count,
                )
                .filter(
                    StripeSubscription.connection_id.in_(connection_ids),
                    StripeSubscription.canceled_at >= month_start,
                    StripeSubscription.canceled_at < month_end,
                )
                .all()
            )
            churn_mrr = sum(
                normalize_to_monthly_cents(amt or 0, interval, count or 1)
                for (amt, interval, count) in churn_rows
            )

            points.append(
                MovementPoint(
                    month_start=month_start,
                    new_mrr_cents=new_mrr,
                    churn_mrr_cents=churn_mrr,
                )
            )
        return points

    @staticmethod
    def activity_feed(
        db: Session, organization_id: int, *, limit: int = 15, days: int = 30
    ) -> List[ActivityEvent]:
        """Recent customer events for the dashboard's activity card.

        Pulls new subscriptions, cancellations, and failed charges in
        the last `days`, joins customer name/email, sorts by timestamp
        descending, returns the top `limit`.
        """
        connection_ids = DashboardService._connection_ids(db, organization_id)
        if not connection_ids:
            return []

        since = _utcnow() - timedelta(days=days)

        new_subs = (
            db.query(StripeSubscription)
            .filter(
                StripeSubscription.connection_id.in_(connection_ids),
                StripeSubscription.stripe_created_at >= since,
            )
            .all()
        )
        canceled_subs = (
            db.query(StripeSubscription)
            .filter(
                StripeSubscription.connection_id.in_(connection_ids),
                StripeSubscription.canceled_at >= since,
            )
            .all()
        )
        failed_charges = (
            db.query(StripeCharge)
            .filter(
                StripeCharge.connection_id.in_(connection_ids),
                StripeCharge.status == "failed",
                StripeCharge.stripe_created_at >= since,
            )
            .all()
        )

        # One lookup, all customers referenced.
        customer_ids = {s.stripe_customer_id for s in new_subs}
        customer_ids |= {s.stripe_customer_id for s in canceled_subs}
        customer_ids |= {
            c.stripe_customer_id for c in failed_charges if c.stripe_customer_id
        }
        cmap = (
            {
                c.stripe_customer_id: c
                for c in db.query(StripeCustomer)
                .filter(
                    StripeCustomer.connection_id.in_(connection_ids),
                    StripeCustomer.stripe_customer_id.in_(customer_ids),
                )
                .all()
            }
            if customer_ids
            else {}
        )

        events: List[ActivityEvent] = []
        for s in new_subs:
            c = cmap.get(s.stripe_customer_id)
            plan = (s.stripe_metadata or {}).get("plan") if s.stripe_metadata else None
            events.append(
                ActivityEvent(
                    kind="subscription_started",
                    timestamp=s.stripe_created_at,
                    customer_name=c.name if c else None,
                    customer_email=c.email if c else None,
                    amount_cents=normalize_to_monthly_cents(
                        s.amount_per_period, s.interval, s.interval_count
                    ),
                    description=f"Subscribed to {plan}" if plan else "Started subscription",
                )
            )
        for s in canceled_subs:
            c = cmap.get(s.stripe_customer_id)
            events.append(
                ActivityEvent(
                    kind="subscription_canceled",
                    timestamp=s.canceled_at,
                    customer_name=c.name if c else None,
                    customer_email=c.email if c else None,
                    amount_cents=normalize_to_monthly_cents(
                        s.amount_per_period, s.interval, s.interval_count
                    ),
                    description="Canceled subscription",
                )
            )
        for ch in failed_charges:
            c = cmap.get(ch.stripe_customer_id) if ch.stripe_customer_id else None
            events.append(
                ActivityEvent(
                    kind="charge_failed",
                    timestamp=ch.stripe_created_at,
                    customer_name=c.name if c else None,
                    customer_email=c.email if c else None,
                    amount_cents=int(ch.amount or 0),
                    description=ch.failure_message or "Payment failed",
                )
            )

        events.sort(key=lambda e: e.timestamp, reverse=True)
        return events[:limit]

    @staticmethod
    def mrr_trend(db: Session, organization_id: int, months: int = 12) -> List[TrendPoint]:
        """End-of-month MRR for the last N months, oldest first."""
        connection_ids = DashboardService._connection_ids(db, organization_id)
        if not connection_ids:
            return []

        now = _utcnow()
        # Start from the first day of the current month, go back N-1 months.
        current_month_start = now.replace(day=1, hour=0, minute=0, second=0, microsecond=0)
        points: List[TrendPoint] = []
        for i in range(months - 1, -1, -1):
            month_start = current_month_start - relativedelta(months=i)
            # Sample MRR at the end of that month (or `now` for the current month).
            sample_at = min(
                month_start + relativedelta(months=1) - timedelta(seconds=1),
                now,
            )
            mrr = DashboardService._mrr_at(db, connection_ids, sample_at)
            points.append(TrendPoint(date=month_start, mrr_cents=mrr))
        return points

    @staticmethod
    def top_customers(db: Session, organization_id: int, limit: int = 5) -> List[TopCustomer]:
        connection_ids = DashboardService._connection_ids(db, organization_id)
        if not connection_ids:
            return []

        ninety_days_ago = _utcnow() - timedelta(days=90)

        rows = (
            db.query(
                StripeCharge.stripe_customer_id,
                func.sum(StripeCharge.amount).label("total"),
            )
            .filter(
                StripeCharge.connection_id.in_(connection_ids),
                StripeCharge.stripe_customer_id.isnot(None),
                StripeCharge.status == "succeeded",
                StripeCharge.stripe_created_at >= ninety_days_ago,
            )
            .group_by(StripeCharge.stripe_customer_id)
            .order_by(desc("total"))
            .limit(limit)
            .all()
        )
        if not rows:
            return []

        customer_ids = [r[0] for r in rows]
        customers = (
            db.query(StripeCustomer)
            .filter(
                StripeCustomer.connection_id.in_(connection_ids),
                StripeCustomer.stripe_customer_id.in_(customer_ids),
            )
            .all()
        )
        customer_map = {c.stripe_customer_id: c for c in customers}

        return [
            TopCustomer(
                stripe_customer_id=cid,
                name=customer_map.get(cid).name if customer_map.get(cid) else None,
                email=customer_map.get(cid).email if customer_map.get(cid) else None,
                total_revenue_cents=int(total or 0),
            )
            for cid, total in rows
        ]

    @staticmethod
    def recent_activity(
        db: Session, organization_id: int, days: int = 7
    ) -> dict:
        """Compact summary used by the AI weekly review prompt."""
        connection_ids = DashboardService._connection_ids(db, organization_id)
        if not connection_ids:
            return {
                "new_customers": 0,
                "churned_customers": 0,
                "revenue_cents": 0,
                "top_new_customers": [],
                "top_churned_customers": [],
            }

        now = _utcnow()
        since = now - timedelta(days=days)

        # New active subscriptions in window.
        new_subs = (
            db.query(StripeSubscription)
            .filter(
                StripeSubscription.connection_id.in_(connection_ids),
                StripeSubscription.stripe_created_at >= since,
                StripeSubscription.stripe_created_at <= now,
            )
            .all()
        )

        # Churned subscriptions in window.
        churned_subs = (
            db.query(StripeSubscription)
            .filter(
                StripeSubscription.connection_id.in_(connection_ids),
                StripeSubscription.canceled_at >= since,
                StripeSubscription.canceled_at <= now,
            )
            .all()
        )

        revenue_cents = (
            db.query(func.coalesce(func.sum(StripeCharge.amount), 0))
            .filter(
                StripeCharge.connection_id.in_(connection_ids),
                StripeCharge.status == "succeeded",
                StripeCharge.stripe_created_at >= since,
                StripeCharge.stripe_created_at <= now,
            )
            .scalar()
            or 0
        )

        # Customer name lookup for the cited subs.
        customer_ids = {s.stripe_customer_id for s in new_subs + churned_subs}
        customers = (
            db.query(StripeCustomer)
            .filter(
                StripeCustomer.connection_id.in_(connection_ids),
                StripeCustomer.stripe_customer_id.in_(customer_ids),
            )
            .all()
        )
        customer_map = {c.stripe_customer_id: c for c in customers}

        def describe(sub: StripeSubscription) -> dict:
            cust = customer_map.get(sub.stripe_customer_id)
            return {
                "customer_name": cust.name if cust else None,
                "customer_email": cust.email if cust else None,
                "mrr_cents": normalize_to_monthly_cents(
                    sub.amount_per_period, sub.interval, sub.interval_count
                ),
                "status": sub.status,
            }

        # Sort by MRR impact, take top 5 of each.
        new_subs_sorted = sorted(
            new_subs,
            key=lambda s: normalize_to_monthly_cents(s.amount_per_period, s.interval, s.interval_count),
            reverse=True,
        )[:5]
        churned_subs_sorted = sorted(
            churned_subs,
            key=lambda s: normalize_to_monthly_cents(s.amount_per_period, s.interval, s.interval_count),
            reverse=True,
        )[:5]

        return {
            "new_customers": len({s.stripe_customer_id for s in new_subs}),
            "churned_customers": len({s.stripe_customer_id for s in churned_subs}),
            "revenue_cents": int(revenue_cents),
            "top_new_customers": [describe(s) for s in new_subs_sorted],
            "top_churned_customers": [describe(s) for s in churned_subs_sorted],
        }
