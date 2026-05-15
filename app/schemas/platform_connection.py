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
