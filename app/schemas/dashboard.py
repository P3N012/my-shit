"""Pydantic shapes for /api/v1/dashboard/*."""

from datetime import datetime
from typing import List, Optional

from pydantic import BaseModel, ConfigDict


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

    failed_payments_count: int = 0
    failed_payments_cents: int = 0

    period_days: int


class TrendPoint(BaseModel):
    date: datetime
    mrr_cents: int


class TrendsResponse(BaseModel):
    points: List[TrendPoint]


class MovementPoint(BaseModel):
    month_start: datetime
    new_mrr_cents: int
    churn_mrr_cents: int


class MovementsResponse(BaseModel):
    points: List[MovementPoint]


class TopCustomerEntry(BaseModel):
    stripe_customer_id: str
    name: Optional[str]
    email: Optional[str]
    total_revenue_cents: int


class TopCustomersResponse(BaseModel):
    customers: List[TopCustomerEntry]


class ActivityEventResponse(BaseModel):
    kind: str
    timestamp: datetime
    customer_name: Optional[str]
    customer_email: Optional[str]
    amount_cents: int
    description: str


class ActivityResponse(BaseModel):
    events: List[ActivityEventResponse]


class CustomerSubscription(BaseModel):
    stripe_subscription_id: str
    status: str
    currency: Optional[str]
    amount_per_period: int
    interval: Optional[str]
    interval_count: int
    current_period_end: Optional[datetime]
    cancel_at_period_end: bool
    canceled_at: Optional[datetime]
    started_at: Optional[datetime]

    model_config = ConfigDict(from_attributes=True)


class CustomerCharge(BaseModel):
    stripe_charge_id: str
    amount: int
    amount_refunded: int
    currency: str
    status: str
    paid: bool
    refunded: bool
    stripe_created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class CustomerDetailResponse(BaseModel):
    stripe_customer_id: str
    name: Optional[str]
    email: Optional[str]
    currency: Optional[str]
    delinquent: bool
    stripe_created_at: datetime
    current_mrr_cents: int
    lifetime_value_cents: int
    subscriptions: List[CustomerSubscription]
    charges: List[CustomerCharge]
