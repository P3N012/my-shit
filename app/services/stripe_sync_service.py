"""
Stripe → DB sync.

Pulls customers, subscriptions, and charges (last 90 days) from a
connected Stripe account and upserts them into our mirrored tables.
Uses the platform-key + `stripe_account` header pattern so we never
depend on the connected-account OAuth token after the initial grant —
if the user revokes us, subsequent calls fail cleanly with an
account-not-authorized error.

This is idempotent: re-running the sync is safe. We upsert by
`(connection_id, stripe_*_id)`.
"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any, Dict, Optional

import stripe
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.platform_connection import (
    AUTH_RESTRICTED_KEY,
    CONN_ACTIVE,
    CONN_ERROR,
    PlatformConnection,
)
from app.models.stripe_data import (
    SYNC_FAILED,
    SYNC_RUNNING,
    SYNC_SUCCESS,
    StripeCharge,
    StripeCustomer,
    StripeSubscription,
    SyncLog,
)

CHARGE_LOOKBACK_DAYS = 90


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _ts(value: Optional[int]) -> Optional[datetime]:
    """Stripe timestamps are unix seconds. Convert to tz-aware UTC."""
    if value is None:
        return None
    return datetime.fromtimestamp(value, tz=timezone.utc)


def _safe_get(obj: Any, *path: str, default: Any = None) -> Any:
    """Navigate a (possibly stripe-object) dict path safely."""
    cur = obj
    for key in path:
        if cur is None:
            return default
        if hasattr(cur, "get"):
            cur = cur.get(key)
        else:
            return default
    return cur if cur is not None else default


def _extract_subscription_amount(sub: Any) -> int:
    """Total amount per period in cents. Sum across all subscription items."""
    items = _safe_get(sub, "items", "data", default=[]) or []
    total = 0
    for item in items:
        price = _safe_get(item, "price", default={})
        unit_amount = _safe_get(price, "unit_amount", default=0) or 0
        quantity = _safe_get(item, "quantity", default=1) or 1
        total += int(unit_amount) * int(quantity)
    return total


def _extract_interval(sub: Any) -> tuple[Optional[str], int]:
    """Recurring interval (month/year/week/day) + count, from the first item."""
    items = _safe_get(sub, "items", "data", default=[]) or []
    if not items:
        return None, 1
    recurring = _safe_get(items[0], "price", "recurring", default={})
    return (
        _safe_get(recurring, "interval"),
        int(_safe_get(recurring, "interval_count", default=1) or 1),
    )


class StripeSyncService:
    @staticmethod
    def _configure_auth(connection: PlatformConnection) -> Dict[str, Any]:
        """
        Set `stripe.api_key` for this connection and return the extra
        kwargs every Stripe call needs.

        - restricted_key: authenticate *as* the account with its read-only
          key — no `stripe_account` header.
        - oauth (Connect): authenticate with the platform secret key and
          target the connected account via `stripe_account`.
        """
        if connection.auth_method == AUTH_RESTRICTED_KEY:
            stripe.api_key = connection.access_token
            return {}
        if not settings.STRIPE_SECRET_KEY:
            raise RuntimeError("STRIPE_SECRET_KEY is not configured.")
        stripe.api_key = settings.STRIPE_SECRET_KEY
        return {"stripe_account": connection.account_id}

    @staticmethod
    def sync(db: Session, connection: PlatformConnection) -> SyncLog:
        """
        Sync one connected Stripe account. Creates one SyncLog row, runs
        the three top-level resource pulls, and writes stats back.

        Raises on Stripe API failure; the calling worker translates that
        into a failed SyncLog + connection.status='error'.
        """
        # Set the API key + per-call kwargs for this connection's auth
        # method before doing anything that touches Stripe.
        call_kwargs = StripeSyncService._configure_auth(connection)

        log = SyncLog(connection_id=connection.id, status=SYNC_RUNNING)
        db.add(log)
        db.commit()
        db.refresh(log)

        stats: Dict[str, int] = {"customers": 0, "subscriptions": 0, "charges": 0}

        try:
            for cust in stripe.Customer.list(
                limit=100, **call_kwargs
            ).auto_paging_iter():
                StripeSyncService._upsert_customer(db, connection, cust)
                stats["customers"] += 1

            for sub in stripe.Subscription.list(
                status="all", limit=100, **call_kwargs
            ).auto_paging_iter():
                StripeSyncService._upsert_subscription(db, connection, sub)
                stats["subscriptions"] += 1

            cutoff = int(
                (_utcnow() - timedelta(days=CHARGE_LOOKBACK_DAYS)).timestamp()
            )
            for charge in stripe.Charge.list(
                created={"gte": cutoff},
                limit=100,
                **call_kwargs,
            ).auto_paging_iter():
                StripeSyncService._upsert_charge(db, connection, charge)
                stats["charges"] += 1

            db.commit()

            log.status = SYNC_SUCCESS
            log.stats_json = stats
            log.finished_at = _utcnow()

            connection.status = CONN_ACTIVE
            connection.last_synced_at = _utcnow()
            connection.last_sync_status = SYNC_SUCCESS
            connection.error_message = None
            db.commit()
            db.refresh(log)
            return log

        except Exception as exc:
            db.rollback()
            log.status = SYNC_FAILED
            log.error = str(exc)[:5000]
            log.finished_at = _utcnow()
            log.stats_json = stats
            connection.status = CONN_ERROR
            connection.last_sync_status = SYNC_FAILED
            connection.error_message = str(exc)[:1000]
            db.commit()
            raise

    # -------- per-resource upserts -----------------------------------------

    @staticmethod
    def _upsert_customer(
        db: Session, connection: PlatformConnection, obj: Any
    ) -> None:
        stripe_id = obj["id"]
        row: Optional[StripeCustomer] = (
            db.query(StripeCustomer)
            .filter(
                StripeCustomer.connection_id == connection.id,
                StripeCustomer.stripe_customer_id == stripe_id,
            )
            .first()
        )
        if row is None:
            row = StripeCustomer(
                connection_id=connection.id,
                stripe_customer_id=stripe_id,
                stripe_created_at=_ts(obj.get("created")) or _utcnow(),
            )
            db.add(row)

        row.email = obj.get("email")
        row.name = obj.get("name")
        row.description = obj.get("description")
        row.currency = obj.get("currency")
        row.balance = int(obj.get("balance") or 0)
        row.delinquent = bool(obj.get("delinquent"))
        row.livemode = bool(obj.get("livemode"))
        row.stripe_metadata = dict(obj.get("metadata") or {})
        row.synced_at = _utcnow()

    @staticmethod
    def _upsert_subscription(
        db: Session, connection: PlatformConnection, obj: Any
    ) -> None:
        stripe_id = obj["id"]
        row: Optional[StripeSubscription] = (
            db.query(StripeSubscription)
            .filter(
                StripeSubscription.connection_id == connection.id,
                StripeSubscription.stripe_subscription_id == stripe_id,
            )
            .first()
        )
        if row is None:
            row = StripeSubscription(
                connection_id=connection.id,
                stripe_subscription_id=stripe_id,
                stripe_customer_id=obj.get("customer") or "",
                stripe_created_at=_ts(obj.get("created")) or _utcnow(),
                status=obj.get("status") or "unknown",
            )
            db.add(row)

        interval, interval_count = _extract_interval(obj)
        row.stripe_customer_id = obj.get("customer") or row.stripe_customer_id
        row.status = obj.get("status") or row.status
        row.currency = obj.get("currency")
        row.amount_per_period = _extract_subscription_amount(obj)
        row.interval = interval
        row.interval_count = interval_count
        row.current_period_start = _ts(obj.get("current_period_start"))
        row.current_period_end = _ts(obj.get("current_period_end"))
        row.cancel_at_period_end = bool(obj.get("cancel_at_period_end"))
        row.canceled_at = _ts(obj.get("canceled_at"))
        row.started_at = _ts(obj.get("start_date"))
        row.ended_at = _ts(obj.get("ended_at"))
        row.trial_end = _ts(obj.get("trial_end"))
        # Snapshot a slim items array for inspection — don't bloat with full price objects.
        items = _safe_get(obj, "items", "data", default=[]) or []
        row.items_json = [
            {
                "id": _safe_get(it, "id"),
                "price_id": _safe_get(it, "price", "id"),
                "unit_amount": _safe_get(it, "price", "unit_amount"),
                "quantity": _safe_get(it, "quantity", default=1),
            }
            for it in items
        ]
        row.stripe_metadata = dict(obj.get("metadata") or {})
        row.synced_at = _utcnow()

    @staticmethod
    def _upsert_charge(
        db: Session, connection: PlatformConnection, obj: Any
    ) -> None:
        stripe_id = obj["id"]
        row: Optional[StripeCharge] = (
            db.query(StripeCharge)
            .filter(
                StripeCharge.connection_id == connection.id,
                StripeCharge.stripe_charge_id == stripe_id,
            )
            .first()
        )
        if row is None:
            row = StripeCharge(
                connection_id=connection.id,
                stripe_charge_id=stripe_id,
                amount=int(obj.get("amount") or 0),
                currency=obj.get("currency") or "usd",
                status=obj.get("status") or "unknown",
                stripe_created_at=_ts(obj.get("created")) or _utcnow(),
            )
            db.add(row)

        row.stripe_customer_id = obj.get("customer")
        row.amount = int(obj.get("amount") or 0)
        row.amount_refunded = int(obj.get("amount_refunded") or 0)
        row.currency = obj.get("currency") or row.currency
        row.status = obj.get("status") or row.status
        row.paid = bool(obj.get("paid"))
        row.refunded = bool(obj.get("refunded"))
        row.livemode = bool(obj.get("livemode"))
        row.description = obj.get("description")
        row.failure_code = obj.get("failure_code")
        row.failure_message = obj.get("failure_message")
        row.stripe_metadata = dict(obj.get("metadata") or {})
        row.synced_at = _utcnow()
