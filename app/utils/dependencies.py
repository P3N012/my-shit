"""
Authentication Dependencies

FastAPI dependencies for:
- Getting current user from JWT token
- Protecting endpoints (require authentication)
"""

from fastapi import Depends, Header, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from sqlalchemy.orm import Session
from typing import Optional, Sequence

from app.core.database import get_db
from app.core.security import get_user_id_from_token
from app.models.organization import Membership
from app.models.user import User
from app.services.auth_service import AuthService
from app.services.organization_service import OrganizationService

# Security scheme for Swagger UI
security = HTTPBearer()


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Depends(security),
    db: Session = Depends(get_db)
) -> User:
    """
    Get current authenticated user from JWT token.
    
    This dependency extracts the JWT token from the Authorization header,
    verifies it, and returns the corresponding User object.
    
    Usage in routes:
        @router.get("/protected")
        def protected_endpoint(current_user: User = Depends(get_current_user)):
            return {"message": f"Hello {current_user.username}"}
    
    Args:
        credentials: HTTP Bearer credentials (JWT token)
        db: Database session
        
    Returns:
        User object if token is valid
        
    Raises:
        HTTPException: 401 if token invalid or user not found
    """
    # Extract token
    token = credentials.credentials
    
    # Decode token and get user ID
    user_id = get_user_id_from_token(token, is_refresh=False)
    
    if user_id is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Get user from database
    user = AuthService.get_user_by_id(db, user_id)
    
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="User not found",
            headers={"WWW-Authenticate": "Bearer"},
        )
    
    # Check if user is active
    if user.status != "active":
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="User account is not active"
        )
    
    return user


def get_current_active_user(
    current_user: User = Depends(get_current_user)
) -> User:
    """
    Alias for get_current_user (for clarity).
    
    Use this in routes that require an active user.
    """
    return current_user


def get_optional_user(
    credentials: Optional[HTTPAuthorizationCredentials] = Depends(HTTPBearer(auto_error=False)),
    db: Session = Depends(get_db)
) -> Optional[User]:
    """Return the current user if a valid token was provided, None otherwise."""
    if not credentials:
        return None
    try:
        return get_current_user(credentials, db)
    except HTTPException:
        return None


def get_current_membership(
    x_organization_id: Optional[int] = Header(None, alias="X-Organization-Id"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Membership:
    """
    Resolve the active membership for an org-scoped request.

    The client passes the active org via the `X-Organization-Id` header.
    Returns the user's Membership in that org (which carries their role).
    Raises 400 if the header is missing and 403 if the user has no
    membership in the requested org.
    """
    if x_organization_id is None:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="X-Organization-Id header is required",
        )

    membership = OrganizationService.get_membership(
        db, user_id=current_user.id, organization_id=x_organization_id
    )
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No access to this organization",
        )
    return membership


def require_role(*allowed_roles: str):
    """
    Dependency factory: require the active membership to have one of the
    given roles.

        @router.delete("/.../{id}", dependencies=[Depends(require_role("owner", "admin"))])
    """
    allowed: Sequence[str] = allowed_roles

    def _check(
        membership: Membership = Depends(get_current_membership),
    ) -> Membership:
        if membership.role not in allowed:
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Insufficient role for this operation",
            )
        return membership

    return _check