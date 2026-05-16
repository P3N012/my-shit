"""Schemas for /api/v1/connections."""

from datetime import datetime
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, ConfigDict


class ConnectionResponse(BaseModel):
    """Public-safe view of a PlatformConnection — never includes tokens."""
    id: int
    platform: str
    account_id: str
    account_name: Optional[str]
    account_metadata: Optional[Dict[str, Any]]
    status: str
    last_synced_at: Optional[datetime]
    last_sync_status: Optional[str]
    error_message: Optional[str]
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class ConnectionListResponse(BaseModel):
    connections: List[ConnectionResponse]
    total: int


class StripeOAuthInitResponse(BaseModel):
    """Returned by `POST /connections/stripe/connect`. The client should
    navigate the user's browser to `authorization_url`."""
    authorization_url: str
    state: str


class DisconnectResponse(BaseModel):
    message: str


class SyncTriggerResponse(BaseModel):
    """Returned by `POST /connections/{id}/sync` — work was enqueued."""
    sync_log_id: int
    status: str  # "running" at the moment of enqueue


class SyncLogResponse(BaseModel):
    id: int
    connection_id: int
    status: str
    started_at: datetime
    finished_at: Optional[datetime]
    stats: Optional[Dict[str, Any]] = None
    error: Optional[str] = None

    model_config = ConfigDict(from_attributes=True)


class CustomerSummary(BaseModel):
    id: int
    stripe_customer_id: str
    email: Optional[str]
    name: Optional[str]
    currency: Optional[str]
    balance: int
    delinquent: bool
    stripe_created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class SubscriptionSummary(BaseModel):
    id: int
    stripe_subscription_id: str
    stripe_customer_id: str
    status: str
    currency: Optional[str]
    amount_per_period: int  # cents
    interval: Optional[str]
    interval_count: int
    current_period_end: Optional[datetime]
    cancel_at_period_end: bool

    model_config = ConfigDict(from_attributes=True)


class ChargeSummary(BaseModel):
    id: int
    stripe_charge_id: str
    stripe_customer_id: Optional[str]
    amount: int  # cents
    amount_refunded: int
    currency: str
    status: str
    paid: bool
    refunded: bool
    stripe_created_at: datetime

    model_config = ConfigDict(from_attributes=True)
