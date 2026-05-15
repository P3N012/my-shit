"""Organization (tenant) and Membership models.

Every user belongs to one or more organizations through a Membership.
Future product tables (jobs, ai_usage, etc.) reference org_id and
queries are always scoped through the active membership.
"""

from datetime import datetime, timezone

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.orm import relationship

from app.core.database import Base


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class Organization(Base):
    __tablename__ = "organizations"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String, nullable=False)

    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    updated_at = Column(DateTime(timezone=True), default=_utcnow, onupdate=_utcnow)

    memberships = relationship(
        "Membership", back_populates="organization", cascade="all, delete-orphan"
    )

    def __repr__(self):
        return f"<Organization(id={self.id}, name='{self.name}')>"


# Roles in ascending order of privilege.
ROLE_MEMBER = "member"
ROLE_ADMIN = "admin"
ROLE_OWNER = "owner"
ALL_ROLES = (ROLE_MEMBER, ROLE_ADMIN, ROLE_OWNER)


class Membership(Base):
    __tablename__ = "memberships"
    __table_args__ = (
        UniqueConstraint("user_id", "organization_id", name="uq_user_org"),
    )

    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id", ondelete="CASCADE"), nullable=False)
    organization_id = Column(
        Integer, ForeignKey("organizations.id", ondelete="CASCADE"), nullable=False
    )
    role = Column(String, default=ROLE_MEMBER, nullable=False)

    created_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)

    user = relationship("User", back_populates="memberships")
    organization = relationship("Organization", back_populates="memberships")

    def __repr__(self):
        return (
            f"<Membership(user_id={self.user_id}, "
            f"organization_id={self.organization_id}, role='{self.role}')>"
        )
