"""
Authentication service: registration, login, token issuing, refresh rotation.
"""

from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.security import (
    create_access_token,
    create_refresh_token,
    hash_password,
    hash_token,
    verify_password,
)
from app.models.organization import ROLE_OWNER, Membership, Organization
from app.models.user import RefreshToken, User


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class AuthService:
    """Authentication operations."""

    @staticmethod
    def register_user(
        db: Session,
        email: str,
        username: str,
        password: str,
    ) -> User:
        """
        Create a user and their personal organization in one transaction.

        Every user is the owner of at least one org. Subsequent org-scoped
        endpoints can rely on the existence of at least one membership.
        """
        if db.query(User).filter(User.email == email).first():
            raise ValueError("Email already registered")
        if db.query(User).filter(User.username == username).first():
            raise ValueError("Username already taken")

        user = User(
            email=email,
            username=username,
            password_hash=hash_password(password),
            status="active",
            subscription_tier="starter",
            subscription_status="trial",
            trial_ends_at=_utcnow() + timedelta(days=14),
        )
        db.add(user)
        db.flush()  # need user.id for the membership

        org = Organization(name=f"{username}'s workspace")
        db.add(org)
        db.flush()

        db.add(
            Membership(
                user_id=user.id,
                organization_id=org.id,
                role=ROLE_OWNER,
            )
        )
        db.commit()
        db.refresh(user)
        return user

    @staticmethod
    def ensure_demo_user(db: Session) -> User:
        """
        Find or create the shared demo account used by the one-click demo
        login. Idempotent: returns the existing user if it's already there,
        otherwise registers it (which also creates its personal org). The
        seed script calls this before seeding so the demo account gets the
        full synthetic dataset.
        """
        existing = (
            db.query(User)
            .filter(User.email == settings.DEMO_USER_EMAIL)
            .first()
        )
        if existing:
            return existing
        return AuthService.register_user(
            db=db,
            email=settings.DEMO_USER_EMAIL,
            username=settings.DEMO_USER_USERNAME,
            password=settings.DEMO_USER_PASSWORD,
        )

    @staticmethod
    def authenticate_user(
        db: Session,
        email: str,
        password: str,
    ) -> Optional[User]:
        user = db.query(User).filter(User.email == email).first()
        if not user or user.status != "active":
            return None
        if not verify_password(password, user.password_hash):
            return None
        return user

    @staticmethod
    def issue_tokens(db: Session, user_id: int) -> Tuple[str, str]:
        """Issue a new access + refresh token pair and persist the refresh hash."""
        access_token = create_access_token(data={"sub": str(user_id)})
        refresh_token = create_refresh_token(data={"sub": str(user_id)})

        db.add(
            RefreshToken(
                token_hash=hash_token(refresh_token),
                user_id=user_id,
                expires_at=_utcnow()
                + timedelta(days=settings.REFRESH_TOKEN_EXPIRE_DAYS),
            )
        )
        db.commit()

        return access_token, refresh_token

    @staticmethod
    def rotate_refresh_token(
        db: Session,
        refresh_token: str,
    ) -> Optional[Tuple[str, str]]:
        """
        Validate a refresh token, revoke it, and issue a new pair.

        Returns (access_token, refresh_token) on success, None if the
        presented token is unknown or expired. The expiry comparison runs
        in SQL so it works the same on Postgres and SQLite.
        """
        existing = (
            db.query(RefreshToken)
            .filter(
                RefreshToken.token_hash == hash_token(refresh_token),
                RefreshToken.expires_at > _utcnow(),
            )
            .first()
        )
        if not existing:
            return None

        user_id = existing.user_id
        db.delete(existing)
        # issue_tokens commits; this commits the deletion too.
        return AuthService.issue_tokens(db, user_id)

    @staticmethod
    def revoke_refresh_token(db: Session, refresh_token: str) -> bool:
        existing = (
            db.query(RefreshToken)
            .filter(RefreshToken.token_hash == hash_token(refresh_token))
            .first()
        )
        if not existing:
            return False
        db.delete(existing)
        db.commit()
        return True

    @staticmethod
    def get_user_by_id(db: Session, user_id: int) -> Optional[User]:
        return db.query(User).filter(User.id == user_id).first()
