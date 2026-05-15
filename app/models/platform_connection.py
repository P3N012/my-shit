"""
Connected third-party data source (Stripe today; later: Google Ads, GA4, etc).

One row per (organization, platform, external_account_id). The OAuth
state token table backs CSRF protection on the redirect leg of the flow.
"""

from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


# Platform identifiers — kept as plain strings so adding a new source is just a new constant.
PLATFORM_STRIPE = "stripe"

# Connection status
CONN_ACTIVE = "active"
CONN_DISCONNECTED = "disconnected"
CONN_ERROR = "error"


class PlatformConnection(Base):
    __tablename__ = "platform_connections"
    __table_args__ = (
        UniqueConstraint(
            "organization_id", "platform", "account_id", name="uq_org_platform_account"
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    organization_id = Column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="SET NULL"), nullable=True
    )

    platform = Column(String, nullable=False, index=True)

    # External account identifier — for Stripe, this is `acct_xxx`.
    account_id = Column(String, nullable=False)
    account_name = Column(String, nullable=True)
    account_metadata = Column(JSON, nullable=True)

    # OAuth tokens. Stored as plaintext for an MVP — a real production
    # deployment would encrypt these at rest with a KMS-managed key.
    access_token = Column(String, nullable=False)
    refresh_token = Column(String, nullable=True)
    token_expires_at = Column(DateTime(timezone=True), nullable=True)
    scope = Column(String, nullable=True)

    status = Column(String, default=CONN_ACTIVE, nullable=False)
    last_synced_at = Column(DateTime(timezone=True), nullable=True)
    last_sync_status = Column(String, nullable=True)
    error_message = Column(Text, nullable=True)

    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    organization = relationship("Organization")
    user = relationship("User")

    def __repr__(self):
        return (
            f"<PlatformConnection(id={self.id}, org={self.organization_id}, "
            f"platform='{self.platform}', account='{self.account_id}')>"
        )


class OAuthState(Base):
    """Short-lived CSRF token for the OAuth redirect leg.

    Issued when a user clicks "Connect Stripe", consumed on callback.
    Binds the redirect to the user + org that initiated it, so an attacker
    who tricks a victim into hitting the callback URL can't graft a
    Stripe account onto the victim's organization.
    """
    __tablename__ = "oauth_states"

    id = Column(Integer, primary_key=True, index=True)
    state = Column(String, unique=True, index=True, nullable=False)
    platform = Column(String, nullable=False)
    user_id = Column(
        Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False
    )
    organization_id = Column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    expires_at = Column(DateTime(timezone=True), nullable=False)
    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
