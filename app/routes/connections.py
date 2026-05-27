"""
Connected data sources.

  POST /connections/stripe/connect    Begin Stripe Connect OAuth (returns auth URL)
  GET  /connections/stripe/callback   OAuth redirect target (called by Stripe, public)
  GET  /connections                   List the active org's connections
  GET  /connections/{id}              Get one connection
  DELETE /connections/{id}            Disconnect + delete

All routes except `/stripe/callback` are org-scoped via the
`X-Organization-Id` header. The callback is public — Stripe calls it
on the user's behalf — and is bound to the initiating user by the
state token it presents.
"""

import asyncio
import logging
from typing import List

from arq import create_pool
from arq.connections import RedisSettings
from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.organization import Membership
from app.models.platform_connection import PlatformConnection
from app.models.stripe_data import (
    SYNC_RUNNING,
    StripeCharge,
    StripeCustomer,
    StripeSubscription,
    SyncLog,
)
from app.schemas.platform_connection import (
    ChargeSummary,
    ConnectionListResponse,
    ConnectionResponse,
    CustomerSummary,
    DisconnectResponse,
    StripeApiKeyConnectRequest,
    StripeOAuthInitResponse,
    SubscriptionSummary,
    SyncLogResponse,
    SyncTriggerResponse,
)
from app.services.stripe_apikey_service import StripeApiKeyService
from app.services.stripe_oauth_service import StripeOAuthService
from app.services.stripe_sync_service import StripeSyncService
from app.utils.dependencies import get_current_membership

logger = logging.getLogger("api.connections")
router = APIRouter(prefix="/connections", tags=["Connections"])


@router.post(
    "/stripe/connect",
    response_model=StripeOAuthInitResponse,
    responses={503: {"description": "Stripe not configured"}},
)
def stripe_connect(
    membership: Membership = Depends(get_current_membership),
    db: Session = Depends(get_db),
):
    try:
        url, state = StripeOAuthService.init(
            db,
            user_id=membership.user_id,
            organization_id=membership.organization_id,
        )
    except RuntimeError as exc:
        logger.warning(f"Stripe Connect not configured: {exc}")
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Stripe Connect is not configured on this server.",
        )
    return StripeOAuthInitResponse(authorization_url=url, state=state)


@router.post(
    "/stripe/api-key",
    response_model=ConnectionResponse,
    status_code=status.HTTP_201_CREATED,
    responses={400: {"description": "Invalid or non-restricted key"}},
)
def stripe_connect_api_key(
    payload: StripeApiKeyConnectRequest,
    membership: Membership = Depends(get_current_membership),
    db: Session = Depends(get_db),
):
    """
    Connect a Stripe account with a read-only restricted API key (`rk_…`).

    The trust-first alternative to OAuth: the user controls exactly what
    the key can read and can revoke it from their own Stripe dashboard.
    Full secret keys (`sk_…`) are rejected.
    """
    try:
        connection = StripeApiKeyService.connect(
            db,
            user_id=membership.user_id,
            organization_id=membership.organization_id,
            api_key=payload.api_key,
        )
    except ValueError as exc:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(exc))
    return ConnectionResponse.model_validate(connection)


@router.get(
    "/stripe/callback",
    include_in_schema=True,
    response_class=RedirectResponse,
)
def stripe_callback(
    code: str = Query(default=""),
    state: str = Query(default=""),
    error: str = Query(default=""),
    error_description: str = Query(default=""),
    db: Session = Depends(get_db),
):
    """
    Stripe redirects here after the user authorizes (or denies).

    No auth header — the request comes from the user's browser following
    Stripe's redirect. Trust is established by the one-time `state`
    token issued during `/stripe/connect`.

    On success: 302 to `STRIPE_OAUTH_SUCCESS_URL?connection_id=<id>`.
    On failure: 302 to `STRIPE_OAUTH_FAILURE_URL?reason=<msg>`.
    """
    if error:
        msg = error_description or error
        logger.info(f"Stripe Connect denied: {msg}")
        return RedirectResponse(
            url=f"{settings.STRIPE_OAUTH_FAILURE_URL}&reason={msg}", status_code=302
        )

    if not code or not state:
        return RedirectResponse(
            url=f"{settings.STRIPE_OAUTH_FAILURE_URL}&reason=missing_code_or_state",
            status_code=302,
        )

    try:
        connection = StripeOAuthService.handle_callback(db, code=code, state=state)
    except ValueError as exc:
        logger.info(f"Stripe Connect callback failed: {exc}")
        return RedirectResponse(
            url=f"{settings.STRIPE_OAUTH_FAILURE_URL}&reason={exc}", status_code=302
        )
    except RuntimeError as exc:
        logger.warning(f"Stripe Connect callback misconfigured: {exc}")
        return RedirectResponse(
            url=f"{settings.STRIPE_OAUTH_FAILURE_URL}&reason=not_configured",
            status_code=302,
        )

    return RedirectResponse(
        url=f"{settings.STRIPE_OAUTH_SUCCESS_URL}&connection_id={connection.id}",
        status_code=302,
    )


@router.get("", response_model=ConnectionListResponse)
def list_connections(
    membership: Membership = Depends(get_current_membership),
    db: Session = Depends(get_db),
):
    rows = (
        db.query(PlatformConnection)
        .filter(PlatformConnection.organization_id == membership.organization_id)
        .order_by(PlatformConnection.id.asc())
        .all()
    )
    return ConnectionListResponse(
        connections=[ConnectionResponse.model_validate(r) for r in rows],
        total=len(rows),
    )


@router.get("/{connection_id}", response_model=ConnectionResponse)
def get_connection(
    connection_id: int,
    membership: Membership = Depends(get_current_membership),
    db: Session = Depends(get_db),
):
    row = (
        db.query(PlatformConnection)
        .filter(
            PlatformConnection.id == connection_id,
            PlatformConnection.organization_id == membership.organization_id,
        )
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Connection not found")
    return ConnectionResponse.model_validate(row)


@router.delete("/{connection_id}", response_model=DisconnectResponse)
def delete_connection(
    connection_id: int,
    membership: Membership = Depends(get_current_membership),
    db: Session = Depends(get_db),
):
    ok = StripeOAuthService.disconnect(
        db,
        organization_id=membership.organization_id,
        connection_id=connection_id,
    )
    if not ok:
        raise HTTPException(status_code=404, detail="Connection not found")
    return DisconnectResponse(message="Disconnected.")


def _require_connection(
    db: Session, *, connection_id: int, organization_id: int
) -> PlatformConnection:
    """Helper: 404 if the connection is missing or in another org."""
    row = (
        db.query(PlatformConnection)
        .filter(
            PlatformConnection.id == connection_id,
            PlatformConnection.organization_id == organization_id,
        )
        .first()
    )
    if row is None:
        raise HTTPException(status_code=404, detail="Connection not found")
    return row


@router.post(
    "/{connection_id}/sync",
    response_model=SyncTriggerResponse,
)
async def trigger_sync(
    connection_id: int,
    membership: Membership = Depends(get_current_membership),
    db: Session = Depends(get_db),
):
    """
    Trigger a Stripe sync for this connection.

    Tries to enqueue onto Redis (where a long-running `arq` worker would
    pick it up). If Redis is not reachable — typical in a local dev
    setup without the worker running — falls back to running the sync
    **inline** in the request. That adds 5-30s of latency to the
    response but means the dev flow works with zero extra processes.

    Either way: the SyncLog row is the source of truth for what
    happened; `GET /connections/{id}/sync-logs` shows the history.
    """
    connection = _require_connection(
        db, connection_id=connection_id, organization_id=membership.organization_id
    )

    # First: try the async path.
    try:
        pool = await create_pool(RedisSettings.from_dsn(settings.REDIS_URL))
        try:
            await pool.enqueue_job("run_stripe_sync_job", connection.id)
        finally:
            await pool.close()
    except Exception as exc:
        logger.info(
            f"Redis enqueue unavailable ({exc}); falling back to inline sync"
        )
        # Inline fallback — StripeSyncService.sync creates and updates the
        # SyncLog row itself, so we just call it and return what it produced.
        try:
            log = await asyncio.to_thread(StripeSyncService.sync, db, connection)
        except Exception as sync_exc:
            logger.exception("inline sync failed")
            raise HTTPException(
                status_code=status.HTTP_502_BAD_GATEWAY,
                detail=f"Sync failed: {sync_exc}",
            )
        return SyncTriggerResponse(sync_log_id=log.id, status=log.status)

    # Async path: write a pending SyncLog so the client has an ID and the
    # /sync-logs endpoint shows something immediately. The worker will
    # write its own completion row when it runs.
    log = SyncLog(connection_id=connection.id, status=SYNC_RUNNING)
    db.add(log)
    db.commit()
    db.refresh(log)
    return SyncTriggerResponse(sync_log_id=log.id, status=log.status)


@router.get(
    "/{connection_id}/sync-logs",
    response_model=List[SyncLogResponse],
)
def list_sync_logs(
    connection_id: int,
    limit: int = Query(default=20, ge=1, le=100),
    membership: Membership = Depends(get_current_membership),
    db: Session = Depends(get_db),
):
    _require_connection(
        db, connection_id=connection_id, organization_id=membership.organization_id
    )
    rows = (
        db.query(SyncLog)
        .filter(SyncLog.connection_id == connection_id)
        .order_by(SyncLog.id.desc())
        .limit(limit)
        .all()
    )
    return [
        SyncLogResponse(
            id=r.id,
            connection_id=r.connection_id,
            status=r.status,
            started_at=r.started_at,
            finished_at=r.finished_at,
            stats=r.stats_json,
            error=r.error,
        )
        for r in rows
    ]


# ---------------------------------------------------------------------------
# Read endpoints over the synced Stripe data
# ---------------------------------------------------------------------------

@router.get(
    "/{connection_id}/customers",
    response_model=List[CustomerSummary],
)
def list_customers(
    connection_id: int,
    limit: int = Query(default=50, ge=1, le=500),
    membership: Membership = Depends(get_current_membership),
    db: Session = Depends(get_db),
):
    _require_connection(
        db, connection_id=connection_id, organization_id=membership.organization_id
    )
    rows = (
        db.query(StripeCustomer)
        .filter(StripeCustomer.connection_id == connection_id)
        .order_by(StripeCustomer.stripe_created_at.desc())
        .limit(limit)
        .all()
    )
    return [CustomerSummary.model_validate(r) for r in rows]


@router.get(
    "/{connection_id}/subscriptions",
    response_model=List[SubscriptionSummary],
)
def list_subscriptions(
    connection_id: int,
    status_filter: str = Query(default="", alias="status"),
    limit: int = Query(default=50, ge=1, le=500),
    membership: Membership = Depends(get_current_membership),
    db: Session = Depends(get_db),
):
    _require_connection(
        db, connection_id=connection_id, organization_id=membership.organization_id
    )
    q = db.query(StripeSubscription).filter(
        StripeSubscription.connection_id == connection_id
    )
    if status_filter:
        q = q.filter(StripeSubscription.status == status_filter)
    rows = q.order_by(StripeSubscription.stripe_created_at.desc()).limit(limit).all()
    return [SubscriptionSummary.model_validate(r) for r in rows]


@router.get(
    "/{connection_id}/charges",
    response_model=List[ChargeSummary],
)
def list_charges(
    connection_id: int,
    limit: int = Query(default=50, ge=1, le=500),
    membership: Membership = Depends(get_current_membership),
    db: Session = Depends(get_db),
):
    _require_connection(
        db, connection_id=connection_id, organization_id=membership.organization_id
    )
    rows = (
        db.query(StripeCharge)
        .filter(StripeCharge.connection_id == connection_id)
        .order_by(StripeCharge.stripe_created_at.desc())
        .limit(limit)
        .all()
    )
    return [ChargeSummary.model_validate(r) for r in rows]
