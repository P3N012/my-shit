"""Pydantic shapes for /api/v1/dashboard/*."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel


class KpiDelta(BaseModel):
    """Percentage change vs. the previous period.

    `positive` is the *display* flag: for MRR/ARR/customers, a rise is
    good; for churn, a fall is good. The service flips the sign on the
    way out so the UI can render uniformly.
    """
    value_pct: float
    positive: bool


class OverviewResponse(BaseModel):
    mrr_cents: int
    arr_cents: int
    active_customers: int
    churn_rate: float

    mrr_delta: Optional[KpiDelta]
    arr_delta: Optional[KpiDelta]
    customers_delta: Optional[KpiDelta]
    churn_delta: Optional[KpiDelta]

    period_days: int


class TrendPoint(BaseModel):
    date: datetime
    mrr_cents: int


class TrendsResponse(BaseModel):
    points: List[TrendPoint]


class TopCustomerEntry(BaseModel):
    stripe_customer_id: str
    name: Optional[str]
    email: Optional[str]
    total_revenue_cents: int


class TopCustomersResponse(BaseModel):
    customers: List[TopCustomerEntry]
