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

import logging

from fastapi import APIRouter, Depends, HTTPException, Query, status
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.database import get_db
from app.models.organization import Membership
from app.models.platform_connection import PlatformConnection
from app.schemas.platform_connection import (
    ConnectionListResponse,
    ConnectionResponse,
    DisconnectResponse,
    StripeOAuthInitResponse,
)
from app.services.stripe_oauth_service import StripeOAuthService
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
