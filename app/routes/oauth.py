"""
OAuth Routes

API endpoints for OAuth flow:
- POST /oauth/google-ads/connect - Initiate OAuth
- GET /oauth/google-ads/callback - Handle OAuth callback
- GET /connections - List user's connections
- GET /connections/{id} - Get specific connection
- DELETE /connections/{id} - Disconnect platform
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.schemas.oauth import (
    OAuthConnectResponse,
    PlatformConnectionResponse,
    PlatformConnectionListResponse,
    DisconnectResponse,
    SyncTriggerResponse
)
from app.services.oauth_service import OAuthService
from app.services.sync_service import SyncService
from app.utils.dependencies import get_current_user
from app.models.user import User

router = APIRouter(prefix="/oauth", tags=["OAuth"])
connections_router = APIRouter(prefix="/connections", tags=["Connections"])


# ============================================================================
# Google Ads OAuth
# ============================================================================

@router.post(
    "/google-ads/connect",
    response_model=OAuthConnectResponse,
    summary="Connect Google Ads account"
)
def connect_google_ads(
    current_user: User = Depends(get_current_user)
):
    """
    Initiate Google Ads OAuth flow.
    
    **Returns:**
    - Authorization URL to redirect user to
    - State parameter (for CSRF protection)
    
    **Flow:**
    1. Call this endpoint
    2. Redirect user to the `authorization_url`
    3. User authorizes on Google
    4. Google redirects back to callback URL
    """
    authorization_url, state = OAuthService.generate_google_ads_auth_url(
        user_id=current_user.id
    )
    
    return OAuthConnectResponse(
        authorization_url=authorization_url,
        state=state
    )


@router.get(
    "/google-ads/callback",
    summary="Google Ads OAuth callback"
)
def google_ads_callback(
    code: str = Query(..., description="Authorization code from Google"),
    state: str = Query(..., description="State parameter for verification"),
    db: Session = Depends(get_db)
):
    """
    Handle OAuth callback from Google.
    
    **This endpoint is called by Google after user authorizes.**
    
    **Query Parameters:**
    - code: Authorization code
    - state: State for CSRF protection
    
    **Returns:**
    - Redirects to frontend with success/error
    
    **Note:** In production, redirect to your frontend URL.
    For now, returns JSON for testing.
    """
    try:
        connection = OAuthService.handle_google_ads_callback(
            db=db,
            code=code,
            state=state
        )
        
        # In production: redirect to frontend
        # return RedirectResponse(
        #     url=f"http://localhost:3000/connections?success=true&connection_id={connection.id}"
        # )
        
        # For testing: return JSON
        return {
            "message": "Google Ads connected successfully!",
            "connection": PlatformConnectionResponse.model_validate(connection)
        }
        
    except ValueError as e:
        # In production: redirect to frontend with error
        # return RedirectResponse(
        #     url=f"http://localhost:3000/connections?error={str(e)}"
        # )
        
        # For testing: return error
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


# ============================================================================
# Connection Management
# ============================================================================

@connections_router.get(
    "",
    response_model=PlatformConnectionListResponse,
    summary="List all connections"
)
def list_connections(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all platform connections for current user.
    
    **Returns:**
    - List of all connected platforms
    - Total count
    """
    connections = OAuthService.get_user_connections(db, current_user.id)
    
    return PlatformConnectionListResponse(
        connections=[
            PlatformConnectionResponse.model_validate(conn)
            for conn in connections
        ],
        total=len(connections)
    )


@connections_router.get(
    "/{connection_id}",
    response_model=PlatformConnectionResponse,
    summary="Get connection details"
)
def get_connection(
    connection_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get details of a specific connection.
    
    **Returns:**
    - Connection details
    
    **Errors:**
    - 404 if connection not found or not owned by user
    """
    connection = OAuthService.get_connection(db, connection_id, current_user.id)
    
    if not connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Connection not found"
        )
    
    return PlatformConnectionResponse.model_validate(connection)


@connections_router.delete(
    "/{connection_id}",
    response_model=DisconnectResponse,
    summary="Disconnect platform"
)
def disconnect_platform(
    connection_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Disconnect (delete) a platform connection.
    
    **What this does:**
    - Deletes the connection
    - Removes stored tokens
    - Deletes associated campaigns and metrics
    
    **Returns:**
    - Success message
    
    **Errors:**
    - 404 if connection not found
    """
    success = OAuthService.disconnect_platform(db, connection_id, current_user.id)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Connection not found"
        )
    
    return DisconnectResponse(message="Platform disconnected successfully")


@connections_router.post(
    "/{connection_id}/sync",
    response_model=SyncTriggerResponse,
    summary="Trigger manual sync"
)
def trigger_sync(
    connection_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Manually trigger data sync for a platform connection.
    
    **What this does:**
    1. Fetches campaigns from platform (Google Ads/Meta Ads)
    2. Stores/updates campaigns in database
    3. Fetches last 30 days of metrics
    4. Stores/updates metrics in database
    5. Creates sync log
    
    **Returns:**
    - Success message
    - Sync log ID (to check status)
    
    **Errors:**
    - 404 if connection not found
    - 500 if sync fails
    
    **Note:** This may take 10-30 seconds depending on data volume.
    """
    # Get connection
    connection = OAuthService.get_connection(db, connection_id, current_user.id)
    
    if not connection:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Connection not found"
        )
    
    # Check platform and call appropriate sync
    try:
        if connection.platform == "google_ads":
            sync_log = SyncService.sync_google_ads(db, connection)
        else:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Sync not implemented for platform: {connection.platform}"
            )
        
        return SyncTriggerResponse(
            message="Sync completed successfully",
            sync_log_id=sync_log.id
        )
        
    except Exception as e:
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Sync failed: {str(e)}"
        )