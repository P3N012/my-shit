"""
Authentication routes.

  POST /auth/register   Create account
  POST /auth/login      Exchange credentials for tokens
  POST /auth/refresh    Rotate refresh token, return new pair
  POST /auth/logout     Revoke refresh token
  GET  /auth/me         Current user
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.user import User
from app.schemas.auth import (
    ErrorResponse,
    TokenRefreshRequest,
    TokenResponse,
    UserLoginRequest,
    UserRegisterRequest,
    UserRegisterResponse,
    UserResponse,
)
from app.schemas.organization import MembershipResponse
from app.services.auth_service import AuthService
from app.utils.dependencies import get_current_user

router = APIRouter(prefix="/auth", tags=["Authentication"])


def _token_response(access_token: str, refresh_token: str) -> TokenResponse:
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        token_type="bearer",
        expires_in=settings.ACCESS_TOKEN_EXPIRE_MINUTES * 60,
    )


@router.post(
    "/register",
    response_model=UserRegisterResponse,
    status_code=status.HTTP_201_CREATED,
    responses={400: {"model": ErrorResponse}},
)
def register(request: UserRegisterRequest, db: Session = Depends(get_db)):
    try:
        user = AuthService.register_user(
            db=db,
            email=request.email,
            username=request.username,
            password=request.password,
        )
    except ValueError as e:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, detail=str(e))

    return UserRegisterResponse(
        id=user.id,
        email=user.email,
        username=user.username,
        created_at=user.created_at,
        message="User registered successfully",
    )


@router.post(
    "/login",
    response_model=TokenResponse,
    responses={401: {"model": ErrorResponse}},
)
def login(request: UserLoginRequest, db: Session = Depends(get_db)):
    user = AuthService.authenticate_user(
        db=db, email=request.email, password=request.password
    )
    if not user:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, detail="Invalid email or password"
        )

    access_token, refresh_token = AuthService.issue_tokens(db, user.id)
    return _token_response(access_token, refresh_token)


@router.post(
    "/refresh",
    response_model=TokenResponse,
    responses={401: {"model": ErrorResponse}},
)
def refresh_token(request: TokenRefreshRequest, db: Session = Depends(get_db)):
    """
    Rotate the refresh token.

    The presented refresh token is revoked and a brand-new access/refresh
    pair is returned. Clients must replace both tokens on every refresh.
    """
    pair = AuthService.rotate_refresh_token(db, request.refresh_token)
    if not pair:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, detail="Invalid or expired refresh token"
        )

    access_token, new_refresh_token = pair
    return _token_response(access_token, new_refresh_token)


@router.post(
    "/logout",
    status_code=status.HTTP_204_NO_CONTENT,
    responses={401: {"model": ErrorResponse}},
)
def logout(request: TokenRefreshRequest, db: Session = Depends(get_db)):
    if not AuthService.revoke_refresh_token(db, request.refresh_token):
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED, detail="Invalid refresh token"
        )
    return None


@router.get(
    "/me",
    response_model=UserResponse,
    responses={401: {"model": ErrorResponse}},
)
def get_current_user_info(current_user: User = Depends(get_current_user)):
    memberships = [
        MembershipResponse(
            organization_id=m.organization_id,
            organization_name=m.organization.name,
            role=m.role,
        )
        for m in current_user.memberships
    ]
    return UserResponse(
        id=current_user.id,
        email=current_user.email,
        username=current_user.username,
        is_admin=current_user.is_admin,
        status=current_user.status,
        subscription_tier=current_user.subscription_tier,
        subscription_status=current_user.subscription_status,
        created_at=current_user.created_at,
        memberships=memberships,
    )
