"""
Dashboard aggregates. All org-scoped via `X-Organization-Id`.

  GET /dashboard/overview        MRR / ARR / active customers / churn (+ deltas)
  GET /dashboard/trends          12-month MRR trend (end-of-month samples)
  GET /dashboard/top-customers   Top N customers by revenue over the last 90 days
  GET /dashboard/movements       Per-month new vs. churned MRR movements
  GET /dashboard/activity        Recent account activity feed
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.organization import Membership
from app.schemas.dashboard import (
    ActivityEventResponse,
    ActivityResponse,
    KpiDelta,
    MovementPoint,
    MovementsResponse,
    OverviewResponse,
    TopCustomerEntry,
    TopCustomersResponse,
    TrendPoint,
    TrendsResponse,
)
from app.services.dashboard_service import DashboardService
from app.utils.dependencies import get_current_membership

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


def _pct_change(current: float, previous: float) -> float:
    """Signed percent change. Returns 0 when previous is 0 to avoid +inf%."""
    if previous == 0:
        return 0.0
    return (current - previous) / previous * 100.0


def _kpi_delta_positive_rise(current: float, previous: float) -> KpiDelta:
    """Helper for metrics where a rise is good (MRR, ARR, customers)."""
    pct = _pct_change(current, previous)
    return KpiDelta(value_pct=round(pct, 1), positive=pct >= 0)


def _kpi_delta_positive_fall(current: float, previous: float) -> KpiDelta:
    """Helper for metrics where a fall is good (churn rate)."""
    pct = _pct_change(current, previous)
    return KpiDelta(value_pct=round(pct, 1), positive=pct <= 0)


@router.get("/overview", response_model=OverviewResponse)
def overview(
    membership: Membership = Depends(get_current_membership),
    db: Session = Depends(get_db),
):
    o = DashboardService.overview(db, membership.organization_id)
    return OverviewResponse(
        mrr_cents=o.mrr_cents,
        arr_cents=o.arr_cents,
        active_customers=o.active_customers,
        churn_rate=round(o.churn_rate, 4),
        mrr_delta=_kpi_delta_positive_rise(o.mrr_cents, o.mrr_cents_prev),
        arr_delta=_kpi_delta_positive_rise(o.arr_cents, o.mrr_cents_prev * 12),
        customers_delta=_kpi_delta_positive_rise(
            o.active_customers, o.active_customers_prev
        ),
        churn_delta=_kpi_delta_positive_fall(o.churn_rate, o.churn_rate_prev),
        failed_payments_count=o.failed_payments_count,
        failed_payments_cents=o.failed_payments_cents,
        period_days=o.period_days,
    )


@router.get("/trends", response_model=TrendsResponse)
def trends(
    months: int = Query(default=12, ge=1, le=24),
    membership: Membership = Depends(get_current_membership),
    db: Session = Depends(get_db),
):
    points = DashboardService.mrr_trend(db, membership.organization_id, months=months)
    return TrendsResponse(
        points=[TrendPoint(date=p.date, mrr_cents=p.mrr_cents) for p in points]
    )


@router.get("/top-customers", response_model=TopCustomersResponse)
def top_customers(
    limit: int = Query(default=5, ge=1, le=50),
    membership: Membership = Depends(get_current_membership),
    db: Session = Depends(get_db),
):
    rows = DashboardService.top_customers(db, membership.organization_id, limit=limit)
    return TopCustomersResponse(
        customers=[
            TopCustomerEntry(
                stripe_customer_id=r.stripe_customer_id,
                name=r.name,
                email=r.email,
                total_revenue_cents=r.total_revenue_cents,
            )
            for r in rows
        ]
    )


@router.get("/movements", response_model=MovementsResponse)
def movements(
    months: int = Query(default=12, ge=1, le=24),
    membership: Membership = Depends(get_current_membership),
    db: Session = Depends(get_db),
):
    points = DashboardService.mrr_movements(
        db, membership.organization_id, months=months
    )
    return MovementsResponse(
        points=[
            MovementPoint(
                month_start=p.month_start,
                new_mrr_cents=p.new_mrr_cents,
                churn_mrr_cents=p.churn_mrr_cents,
            )
            for p in points
        ]
    )


@router.get("/activity", response_model=ActivityResponse)
def activity(
    limit: int = Query(default=15, ge=1, le=100),
    days: int = Query(default=30, ge=1, le=365),
    membership: Membership = Depends(get_current_membership),
    db: Session = Depends(get_db),
):
    events = DashboardService.activity_feed(
        db, membership.organization_id, limit=limit, days=days
    )
    return ActivityResponse(
        events=[
            ActivityEventResponse(
                kind=e.kind,
                timestamp=e.timestamp,
                customer_name=e.customer_name,
                customer_email=e.customer_email,
                amount_cents=e.amount_cents,
                description=e.description,
            )
            for e in events
        ]
    )
