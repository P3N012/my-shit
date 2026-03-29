"""
Authentication Service

Business logic for user authentication:
- User registration
- User login
- Token management
- User lookup
"""

from sqlalchemy.orm import Session
from datetime import datetime, timedelta
from typing import Optional, Tuple

from app.models.user import User, RefreshToken
from app.core.security import hash_password, verify_password, create_access_token, create_refresh_token
from app.core.config import settings


class AuthService:
    """Service for handling authentication operations"""
    
    @staticmethod
    def register_user(
        db: Session,
        email: str,
        username: str,
        password: str
    ) -> User:
        """
        Register a new user.
        
        Args:
            db: Database session
            email: User email
            username: Username
            password: Plain text password
            
        Returns:
            Created User object
            
        Raises:
            ValueError: If email or username already exists
        """
        # Check if email already exists
        existing_email = db.query(User).filter(User.email == email).first()
        if existing_email:
            raise ValueError("Email already registered")
        
        # Check if username already exists
        existing_username = db.query(User).filter(User.username == username).first()
        if existing_username:
            raise ValueError("Username already taken")
        
        # Hash password
        hashed_password = hash_password(password)
        
        # Create user
        user = User(
            email=email,
            username=username,
            password=hashed_password,
            status="active",
            subscription_tier="starter",
            subscription_status="trial",
            trial_ends_at=datetime.utcnow() + timedelta(days=14)  # 14-day trial
        )
        
        db.add(user)
        db.commit()
        db.refresh(user)
        
        return user
    
    @staticmethod
    def authenticate_user(
        db: Session,
        email: str,
        password: str
    ) -> Optional[User]:
        """
        Authenticate a user by email and password.
        
        Args:
            db: Database session
            email: User email
            password: Plain text password
            
        Returns:
            User object if credentials valid, None otherwise
        """
        # Find user by email
        user = db.query(User).filter(User.email == email).first()
        
        if not user:
            return None
        
        # Check if account is active
        if user.status != "active":
            return None
        
        # Verify password
        if not verify_password(password, user.password):
            return None
        
        return user
    
    @staticmethod
    def create_tokens(
        db: Session,
        user_id: int
    ) -> Tuple[str, str]:
        """
        Create access and refresh tokens for a user.
        
        Args:
            db: Database session
            user_id: User ID
            
        Returns:
            Tuple of (access_token, refresh_token)
        """
        # Create access token
        access_token = create_access_token(data={"sub": str(user_id)})
        
        # Create refresh token
        refresh_token = create_refresh_token(data={"sub": str(user_id)})
        
        # Store refresh token in database
        expires_at = datetime.utcnow() + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS)
        
        db_refresh_token = RefreshToken(
            token=refresh_token,
            user_id=user_id,
            expires_at=expires_at
        )
        
        db.add(db_refresh_token)
        db.commit()
        
        return access_token, refresh_token
    
    @staticmethod
    def verify_refresh_token(
        db: Session,
        refresh_token: str
    ) -> Optional[int]:
        """
        Verify a refresh token and return user ID.
        
        Args:
            db: Database session
            refresh_token: Refresh token string
            
        Returns:
            User ID if token valid, None otherwise
        """
        # Look up token in database
        db_token = db.query(RefreshToken).filter(
            RefreshToken.token == refresh_token
        ).first()
        
        if not db_token:
            return None
        
        # Check if expired
        if db_token.expires_at < datetime.utcnow():
            # Delete expired token
            db.delete(db_token)
            db.commit()
            return None
        
        return db_token.user_id
    
    @staticmethod
    def revoke_refresh_token(
        db: Session,
        refresh_token: str
    ) -> bool:
        """
        Revoke (delete) a refresh token (for logout).
        
        Args:
            db: Database session
            refresh_token: Refresh token to revoke
            
        Returns:
            True if token was revoked, False if not found
        """
        db_token = db.query(RefreshToken).filter(
            RefreshToken.token == refresh_token
        ).first()
        
        if not db_token:
            return False
        
        db.delete(db_token)
        db.commit()
        
        return True
    
    @staticmethod
    def get_user_by_id(
        db: Session,
        user_id: int
    ) -> Optional[User]:
        """
        Get user by ID.
        
        Args:
            db: Database session
            user_id: User ID
            
        Returns:
            User object if found, None otherwise
        """
        return db.query(User).filter(User.id == user_id).first()