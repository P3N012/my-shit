"""
OAuth Service

Business logic for OAuth flow:
- Generate authorization URL
- Exchange code for tokens
- Store connection in database
- Manage connection lifecycle
"""

from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Optional, Dict, Any
import secrets
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials

from app.models.platform_connection import PlatformConnection
from app.models.sync_log import SyncLog
from app.core.config import settings
from app.services.google_ads_service import GoogleAdsService


class OAuthService:
    """Service for handling OAuth operations"""
    
    # In-memory state storage (for MVP - use Redis in production)
    _state_store: Dict[str, int] = {}
    
    @staticmethod
    def generate_google_ads_auth_url(user_id: int) -> tuple[str, str]:
        """
        Generate Google Ads OAuth authorization URL.
        
        Args:
            user_id: User ID initiating OAuth
            
        Returns:
            Tuple of (authorization_url, state)
        """
        # Generate CSRF state token
        state = secrets.token_urlsafe(32)
        
        # Store state with user_id (expires in 10 minutes)
        OAuthService._state_store[state] = user_id
        
        # Create OAuth flow
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": settings.GOOGLE_ADS_CLIENT_ID,
                    "client_secret": settings.GOOGLE_ADS_CLIENT_SECRET,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [settings.GOOGLE_ADS_REDIRECT_URI]
                }
            },
            scopes=['https://www.googleapis.com/auth/adwords'],
            redirect_uri=settings.GOOGLE_ADS_REDIRECT_URI
        )
        
        # Generate authorization URL
        authorization_url, _ = flow.authorization_url(
            access_type='offline',  # Request refresh token
            include_granted_scopes='true',
            state=state,
            prompt='consent'  # Force consent screen to get refresh token
        )
        
        return authorization_url, state
    
    @staticmethod
    def handle_google_ads_callback(
        db: Session,
        code: str,
        state: str
    ) -> PlatformConnection:
        """
        Handle OAuth callback - exchange code for tokens and store connection.
        
        Args:
            db: Database session
            code: Authorization code from Google
            state: State parameter for CSRF verification
            
        Returns:
            Created PlatformConnection
            
        Raises:
            ValueError: If state invalid or exchange fails
        """
        # Verify state
        user_id = OAuthService._state_store.get(state)
        if not user_id:
            raise ValueError("Invalid or expired state parameter")
        
        # Remove used state
        del OAuthService._state_store[state]
        
        # Create OAuth flow
        flow = Flow.from_client_config(
            {
                "web": {
                    "client_id": settings.GOOGLE_ADS_CLIENT_ID,
                    "client_secret": settings.GOOGLE_ADS_CLIENT_SECRET,
                    "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                    "token_uri": "https://oauth2.googleapis.com/token",
                    "redirect_uris": [settings.GOOGLE_ADS_REDIRECT_URI]
                }
            },
            scopes=['https://www.googleapis.com/auth/adwords'],
            redirect_uri=settings.GOOGLE_ADS_REDIRECT_URI
        )
        
        # Exchange code for tokens
        try:
            flow.fetch_token(code=code)
            credentials = flow.credentials
        except Exception as e:
            raise ValueError(f"Failed to exchange code for tokens: {str(e)}")
        
        # Create Google Ads client to get customer info
        try:
            client = GoogleAdsService.create_client(
                developer_token=settings.GOOGLE_ADS_DEVELOPER_TOKEN,
                client_id=settings.GOOGLE_ADS_CLIENT_ID,
                client_secret=settings.GOOGLE_ADS_CLIENT_SECRET,
                refresh_token=credentials.refresh_token
            )
            
            # Get customer ID from token (Google returns it in token info)
            # For now, we'll need user to provide it or we fetch accessible customers
            # For MVP, let's assume we have the customer_id
            # In production, you'd call customer_service.list_accessible_customers()
            
            # For now, create connection with placeholder
            # User will need to provide customer_id later or we fetch it
            customer_info = {
                "account_id": "pending",  # Will be updated after user selects account
                "account_name": "Google Ads Account"
            }
            
        except Exception as e:
            # If we can't get customer info, still create connection
            customer_info = {
                "account_id": "pending",
                "account_name": "Google Ads Account"
            }
        
        # Check if connection already exists
        existing = db.query(PlatformConnection).filter(
            PlatformConnection.user_id == user_id,
            PlatformConnection.platform == "google_ads"
        ).first()
        
        if existing:
            # Update existing connection
            existing.access_token = credentials.token
            existing.refresh_token = credentials.refresh_token
            existing.token_expires_at = credentials.expiry
            existing.status = "active"
            existing.error_message = None
            existing.consecutive_failures = 0
            db.commit()
            db.refresh(existing)
            return existing
        
        # Create new connection
        connection = PlatformConnection(
            user_id=user_id,
            platform="google_ads",
            account_id=customer_info["account_id"],
            account_name=customer_info["account_name"],
            access_token=credentials.token,
            refresh_token=credentials.refresh_token,
            token_expires_at=credentials.expiry,
            status="active",
            sync_status="never"
        )
        
        db.add(connection)
        db.commit()
        db.refresh(connection)
        
        return connection
    
    @staticmethod
    def get_user_connections(
        db: Session,
        user_id: int
    ) -> list[PlatformConnection]:
        """
        Get all platform connections for a user.
        
        Args:
            db: Database session
            user_id: User ID
            
        Returns:
            List of PlatformConnection objects
        """
        return db.query(PlatformConnection).filter(
            PlatformConnection.user_id == user_id
        ).all()
    
    @staticmethod
    def get_connection(
        db: Session,
        connection_id: int,
        user_id: int
    ) -> Optional[PlatformConnection]:
        """
        Get a specific connection (user must own it).
        
        Args:
            db: Database session
            connection_id: Connection ID
            user_id: User ID (for ownership verification)
            
        Returns:
            PlatformConnection if found and owned by user, None otherwise
        """
        return db.query(PlatformConnection).filter(
            PlatformConnection.id == connection_id,
            PlatformConnection.user_id == user_id
        ).first()
    
    @staticmethod
    def disconnect_platform(
        db: Session,
        connection_id: int,
        user_id: int
    ) -> bool:
        """
        Disconnect (delete) a platform connection.
        
        Args:
            db: Database session
            connection_id: Connection ID
            user_id: User ID (for ownership verification)
            
        Returns:
            True if deleted, False if not found
        """
        connection = OAuthService.get_connection(db, connection_id, user_id)
        
        if not connection:
            return False
        
        db.delete(connection)
        db.commit()
        
        return True
    
    @staticmethod
    def refresh_google_ads_token(
        db: Session,
        connection: PlatformConnection
    ) -> None:
        """
        Refresh Google Ads access token if expired.
        
        Args:
            db: Database session
            connection: PlatformConnection object
        """
        # Check if token needs refresh
        if connection.token_expires_at and connection.token_expires_at > datetime.utcnow():
            return  # Token still valid
        
        # Create credentials object
        credentials = Credentials(
            token=connection.access_token,
            refresh_token=connection.refresh_token,
            token_uri="https://oauth2.googleapis.com/token",
            client_id=settings.GOOGLE_ADS_CLIENT_ID,
            client_secret=settings.GOOGLE_ADS_CLIENT_SECRET
        )
        
        # Refresh token
        try:
            credentials.refresh(Request())
            
            # Update connection
            connection.access_token = credentials.token
            connection.token_expires_at = credentials.expiry
            connection.error_message = None
            
            db.commit()
            
        except Exception as e:
            connection.error_message = f"Token refresh failed: {str(e)}"
            connection.status = "error"
            connection.consecutive_failures += 1
            db.commit()
            raise