"""
Authentication Routes

API endpoints for user authentication:
- POST /auth/register - Register new user
- POST /auth/login - Login and get tokens
- POST /auth/refresh - Refresh access token
- POST /auth/logout - Logout (revoke refresh token)
- GET /auth/me - Get current user info
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.config import settings
from app.schemas.auth import (
    UserRegisterRequest,
    UserRegisterResponse,
    UserLoginRequest,
    TokenResponse,
    TokenRefreshRequest,
    UserResponse,
    ErrorResponse
)
from app.services.auth_service import AuthService
from app.utils.dependencies import get_current_user
from app.models.user import User

router = APIRouter(prefix="/auth", tags=["Authentication"])


@router.post(
    "/register",
    response_model=UserRegisterResponse,
    status_code=status.HTTP_201_CREATED,
    responses={
        400: {"model": ErrorResponse, "description": "Email or username already exists"},
    }
)
def register(
    request: UserRegisterRequest,
    db: Session = Depends(get_db)
):
    """
    Register a new user account.
    
    **Requirements:**
    - Email must be valid and unique
    - Username must be 3-50 characters and unique
    - Password must be at least 8 characters
    
    **Returns:**
    - User information
    - Success message
    """
    try:
        user = AuthService.register_user(
            db=db,
            email=request.email,
            username=request.username,
            password=request.password
        )
        
        return UserRegisterResponse(
            id=user.id,
            email=user.email,
            username=user.username,
            created_at=user.created_at,
            message="User registered successfully"
        )
        
    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=str(e)
        )


@router.post(
    "/login",
    response_model=TokenResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Invalid credentials"},
    }
)
def login(
    request: UserLoginRequest,
    db: Session = Depends(get_db)
):
    """
    Login with email and password.
    
    **Returns:**
    - Access token (valid for 30 minutes)
    - Refresh token (valid for 30 days)
    
    **Usage:**
    1. Call this endpoint with email and password
    2. Save the access_token
    3. Include in Authorization header: `Bearer {access_token}`
    4. When access_token expires, use refresh_token to get a new one
    """
    # Authenticate user
    user = AuthService.authenticate_user(
        db=db,
        email=request.email,
        password=request.password
    )
    
    if not user:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid email or password"
        )
    
    # Create tokens
    access_token, refresh_token = AuthService.create_tokens(db, user.id)
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60  # Convert to seconds
    )


@router.post(
    "/refresh",
    response_model=TokenResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Invalid or expired refresh token"},
    }
)
def refresh_token(
    request: TokenRefreshRequest,
    db: Session = Depends(get_db)
):
    """
    Get a new access token using refresh token.
    
    **When to use:**
    - When your access_token expires (after 30 minutes)
    - You'll get a 401 error on protected endpoints
    - Use this endpoint to get a new access_token
    
    **Returns:**
    - New access_token
    - Same refresh_token (still valid)
    """
    # Verify refresh token
    user_id = AuthService.verify_refresh_token(db, request.refresh_token)
    
    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired refresh token"
        )
    
    # Create new access token (keep same refresh token)
    from app.core.security import create_access_token
    access_token = create_access_token(data={"sub": str(user_id)})
    
    return TokenResponse(
        access_token=access_token,
        refresh_token=request.refresh_token,  # Return same refresh token
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60
    )


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={
        401: {"model": ErrorResponse, "description": "Invalid refresh token"},
    }
)
def logout(
    request: TokenRefreshRequest,
    db: Session = Depends(get_db)
):
    """
    Logout by revoking refresh token.
    
    **What this does:**
    - Deletes the refresh_token from database
    - You won't be able to use it to get new access_tokens
    
    **Note:**
    - Access tokens can't be revoked (they expire after 30 minutes)
    - For complete logout, delete tokens from client side too
    """
    success = AuthService.revoke_refresh_token(db, request.refresh_token)
    
    if not success:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid refresh token"
        )
    
    return None  # 204 No Content


@router.get(
    "/me",
    response_model=UserResponse,
    responses={
        401: {"model": ErrorResponse, "description": "Not authenticated"},
    }
)
def get_current_user_info(
    current_user: User = Depends(get_current_user)
):
    """
    Get current authenticated user information.
    
    **Requires:** Valid access_token in Authorization header
    
    **Usage:**
    ```
    Authorization: Bearer {your_access_token}
    ```
    
    **Returns:**
    - User profile information
    - Account status
    - Subscription details
    """
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        username=current_user.username,
        is_admin=current_user.is_admin,
        status=current_user.status,
        subscription_tier=current_user.subscription_tier,
        subscription_status=current_user.subscription_status,
        created_at=current_user.created_at
    )