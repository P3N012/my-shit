"""
Mirrored Stripe entities + sync audit log.

Each row is scoped to a `platform_connections.id` so the same Stripe
customer ID can exist independently under different connected accounts
without colliding. Amounts are stored as cents (Stripe's native unit) —
never convert to dollars at the storage layer; format at the read site.
"""

from datetime import datetime, timezone

from sqlalchemy import (
    JSON,
    BigInteger,
    Boolean,
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


# Sync run status
SYNC_RUNNING = "running"
SYNC_SUCCESS = "success"
SYNC_FAILED = "failed"


class StripeCustomer(Base):
    __tablename__ = "stripe_customers"
    __table_args__ = (
        UniqueConstraint(
            "connection_id", "stripe_customer_id", name="uq_connection_customer"
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    connection_id = Column(
        Integer,
        ForeignKey("platform_connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    stripe_customer_id = Column(String, nullable=False, index=True)

    email = Column(String, nullable=True)
    name = Column(String, nullable=True)
    description = Column(Text, nullable=True)
    currency = Column(String, nullable=True)
    balance = Column(BigInteger, default=0, nullable=False)  # cents
    delinquent = Column(Boolean, default=False, nullable=False)
    livemode = Column(Boolean, default=False, nullable=False)
    stripe_metadata = Column(JSON, nullable=True)

    stripe_created_at = Column(DateTime(timezone=True), nullable=False)
    synced_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)

    connection = relationship("PlatformConnection")


class StripeSubscription(Base):
    __tablename__ = "stripe_subscriptions"
    __table_args__ = (
        UniqueConstraint(
            "connection_id",
            "stripe_subscription_id",
            name="uq_connection_subscription",
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    connection_id = Column(
        Integer,
        ForeignKey("platform_connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    stripe_subscription_id = Column(String, nullable=False, index=True)
    stripe_customer_id = Column(String, nullable=False, index=True)

    # Lifecycle. Stripe values: active / past_due / unpaid / canceled
    #                         / incomplete / incomplete_expired / trialing / paused.
    status = Column(String, nullable=False, index=True)
    currency = Column(String, nullable=True)

    # Total cost for ONE billing period, in cents. For an MRR calc,
    # normalize by interval / interval_count at the read site.
    amount_per_period = Column(BigInteger, default=0, nullable=False)
    interval = Column(String, nullable=True)  # month / year / week / day
    interval_count = Column(Integer, default=1, nullable=False)

    current_period_start = Column(DateTime(timezone=True), nullable=True)
    current_period_end = Column(DateTime(timezone=True), nullable=True)
    cancel_at_period_end = Column(Boolean, default=False, nullable=False)
    canceled_at = Column(DateTime(timezone=True), nullable=True)
    started_at = Column(DateTime(timezone=True), nullable=True)
    ended_at = Column(DateTime(timezone=True), nullable=True)
    trial_end = Column(DateTime(timezone=True), nullable=True)

    items_json = Column(JSON, nullable=True)
    stripe_metadata = Column(JSON, nullable=True)

    stripe_created_at = Column(DateTime(timezone=True), nullable=False, index=True)
    synced_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)

    connection = relationship("PlatformConnection")


class StripeCharge(Base):
    __tablename__ = "stripe_charges"
    __table_args__ = (
        UniqueConstraint(
            "connection_id", "stripe_charge_id", name="uq_connection_charge"
        ),
    )

    id = Column(Integer, primary_key=True, index=True)
    connection_id = Column(
        Integer,
        ForeignKey("platform_connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    stripe_charge_id = Column(String, nullable=False, index=True)
    stripe_customer_id = Column(String, nullable=True, index=True)

    amount = Column(BigInteger, nullable=False)  # cents
    amount_refunded = Column(BigInteger, default=0, nullable=False)
    currency = Column(String, nullable=False)

    status = Column(String, nullable=False, index=True)  # succeeded / failed / pending
    paid = Column(Boolean, default=False, nullable=False)
    refunded = Column(Boolean, default=False, nullable=False)
    livemode = Column(Boolean, default=False, nullable=False)

    description = Column(Text, nullable=True)
    failure_code = Column(String, nullable=True)
    failure_message = Column(Text, nullable=True)
    stripe_metadata = Column(JSON, nullable=True)

    stripe_created_at = Column(DateTime(timezone=True), nullable=False, index=True)
    synced_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)

    connection = relationship("PlatformConnection")


class SyncLog(Base):
    """One row per sync run. The connection itself carries the
    most-recent state; this table is the audit trail."""

    __tablename__ = "sync_logs"

    id = Column(Integer, primary_key=True, index=True)
    connection_id = Column(
        Integer,
        ForeignKey("platform_connections.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    status = Column(String, nullable=False, index=True)  # running / success / failed
    started_at = Column(DateTime(timezone=True), default=_utcnow, nullable=False)
    finished_at = Column(DateTime(timezone=True), nullable=True)
    stats_json = Column(JSON, nullable=True)  # {customers: 12, subscriptions: 5, ...}
    error = Column(Text, nullable=True)

    connection = relationship("PlatformConnection")
