"""
OAuth Schemas

Pydantic models for OAuth flow request/response validation.
"""

from pydantic import BaseModel, Field, HttpUrl
from typing import Optional
from datetime import datetime


# ============================================================================
# OAuth Initiation
# ============================================================================

class OAuthConnectResponse(BaseModel):
    """Response for OAuth initiation"""
    authorization_url: str = Field(..., description="URL to redirect user to for authorization")
    state: str = Field(..., description="State parameter for CSRF protection")
    
    class Config:
        json_schema_extra = {
            "example": {
                "authorization_url": "https://accounts.google.com/o/oauth2/auth?client_id=...",
                "state": "random_state_string_12345"
            }
        }


# ============================================================================
# OAuth Callback
# ============================================================================

class OAuthCallbackRequest(BaseModel):
    """Request from OAuth callback (query parameters)"""
    code: str = Field(..., description="Authorization code from OAuth provider")
    state: str = Field(..., description="State parameter for verification")
    
    class Config:
        json_schema_extra = {
            "example": {
                "code": "4/0AY0e-g7...",
                "state": "random_state_string_12345"
            }
        }


# ============================================================================
# Platform Connection
# ============================================================================

class PlatformConnectionResponse(BaseModel):
    """Response for platform connection"""
    id: int
    platform: str
    account_id: str
    account_name: Optional[str]
    status: str
    last_sync_at: Optional[datetime]
    created_at: datetime
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": 1,
                "platform": "google_ads",
                "account_id": "1234567890",
                "account_name": "My Google Ads Account",
                "status": "active",
                "last_sync_at": "2026-02-27T10:30:00",
                "created_at": "2026-02-27T10:00:00"
            }
        }


class PlatformConnectionListResponse(BaseModel):
    """Response for listing all connections"""
    connections: list[PlatformConnectionResponse]
    total: int
    
    class Config:
        json_schema_extra = {
            "example": {
                "connections": [
                    {
                        "id": 1,
                        "platform": "google_ads",
                        "account_id": "1234567890",
                        "account_name": "My Ads Account",
                        "status": "active",
                        "last_sync_at": "2026-02-27T10:30:00",
                        "created_at": "2026-02-27T10:00:00"
                    }
                ],
                "total": 1
            }
        }


# ============================================================================
# Connection Management
# ============================================================================

class DisconnectResponse(BaseModel):
    """Response for disconnecting a platform"""
    message: str = Field(default="Platform disconnected successfully")
    
    class Config:
        json_schema_extra = {
            "example": {
                "message": "Platform disconnected successfully"
            }
        }


class SyncTriggerResponse(BaseModel):
    """Response for triggering manual sync"""
    message: str = Field(default="Sync started")
    sync_log_id: int
    
    class Config:
        json_schema_extra = {
            "example": {
                "message": "Sync started",
                "sync_log_id": 42
            }
        }