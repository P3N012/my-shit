"""
Stripe Connect OAuth.

The flow (Standard Connect, OAuth-style):

  1. Client calls POST /connections/stripe/connect. We mint a state
     token bound to (user_id, organization_id), expire in 10 min, and
     return a Stripe authorization URL.
  2. Browser navigates to Stripe, user authorizes, Stripe redirects to
     our callback with `code` + `state`.
  3. We look up state, consume it, exchange the code for tokens via
     Stripe's token endpoint, and create/update a PlatformConnection.
  4. Callback finally 302s the browser to a frontend URL.

Standard Connect access tokens **do not expire** under normal use, so
we don't need refresh-token rotation here. We still store the refresh
token Stripe returns in case the connection is later promoted to a
flow that needs it.
"""

from __future__ import annotations

import secrets
from datetime import datetime, timedelta, timezone
from typing import Optional, Tuple
from urllib.parse import urlencode

import stripe
from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.platform_connection import (
    CONN_ACTIVE,
    PLATFORM_STRIPE,
    OAuthState,
    PlatformConnection,
)


STATE_TTL_MINUTES = 10
STRIPE_AUTHORIZE_URL = "https://connect.stripe.com/oauth/authorize"


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


class StripeOAuthService:
    @staticmethod
    def init(
        db: Session,
        *,
        user_id: int,
        organization_id: int,
    ) -> Tuple[str, str]:
        """Mint a state token and return the Stripe authorization URL."""
        if not settings.STRIPE_CONNECT_CLIENT_ID:
            raise RuntimeError("STRIPE_CONNECT_CLIENT_ID is not configured.")

        token = secrets.token_urlsafe(32)
        db.add(
            OAuthState(
                state=token,
                platform=PLATFORM_STRIPE,
                user_id=user_id,
                organization_id=organization_id,
                expires_at=_utcnow() + timedelta(minutes=STATE_TTL_MINUTES),
            )
        )
        db.commit()

        params = {
            "response_type": "code",
            "client_id": settings.STRIPE_CONNECT_CLIENT_ID,
            # Stripe gates the `read_only` scope behind a support request
            # for new Connect platforms — `read_write` is what's actually
            # granted by default. We don't make any write calls anywhere
            # in the codebase (StripeSyncService only reads), so this is
            # purely a server-side policy concession, not a real
            # privilege expansion on our side.
            "scope": "read_write",
            "state": token,
            "redirect_uri": settings.STRIPE_OAUTH_REDIRECT_URI,
        }
        return f"{STRIPE_AUTHORIZE_URL}?{urlencode(params)}", token

    @staticmethod
    def handle_callback(
        db: Session,
        *,
        code: str,
        state: str,
    ) -> PlatformConnection:
        """
        Exchange `code` for tokens and persist a PlatformConnection.

        Raises ValueError for any user-visible failure (bad state, expired,
        Stripe rejection). The route layer surfaces the message.
        """
        row: Optional[OAuthState] = (
            db.query(OAuthState)
            .filter(
                OAuthState.state == state,
                OAuthState.platform == PLATFORM_STRIPE,
                OAuthState.expires_at > _utcnow(),
            )
            .first()
        )
        if row is None:
            raise ValueError("Invalid or expired state token.")

        user_id = row.user_id
        organization_id = row.organization_id
        db.delete(row)  # one-time use
        db.commit()

        if not settings.STRIPE_SECRET_KEY:
            raise RuntimeError("STRIPE_SECRET_KEY is not configured.")

        # Exchange the code. stripe-python exposes this via OAuth.token.
        stripe.api_key = settings.STRIPE_SECRET_KEY
        try:
            token_response = stripe.OAuth.token(
                grant_type="authorization_code", code=code
            )
        except stripe.oauth_error.OAuthError as exc:
            raise ValueError(f"Stripe rejected the authorization code: {exc}")
        except Exception as exc:
            raise ValueError(f"Failed to exchange code with Stripe: {exc}")

        stripe_user_id: str = token_response["stripe_user_id"]
        access_token: str = token_response["access_token"]
        refresh_token: Optional[str] = token_response.get("refresh_token")
        scope: Optional[str] = token_response.get("scope")
        livemode: bool = bool(token_response.get("livemode", False))

        # Try to fetch the account display name. Non-fatal if it fails.
        account_name: Optional[str] = None
        account_metadata = {"livemode": livemode}
        try:
            account = stripe.Account.retrieve(stripe_user_id)
            account_name = (
                account.get("business_profile", {}).get("name")
                or account.get("settings", {}).get("dashboard", {}).get("display_name")
                or account.get("email")
            )
            account_metadata["country"] = account.get("country")
            account_metadata["default_currency"] = account.get("default_currency")
        except Exception:
            # Don't fail the whole flow over a friendly-name lookup.
            pass

        # Upsert: if the org already has a connection to this Stripe
        # account, refresh tokens rather than create a duplicate.
        existing: Optional[PlatformConnection] = (
            db.query(PlatformConnection)
            .filter(
                PlatformConnection.organization_id == organization_id,
                PlatformConnection.platform == PLATFORM_STRIPE,
                PlatformConnection.account_id == stripe_user_id,
            )
            .first()
        )
        if existing:
            existing.access_token = access_token
            existing.refresh_token = refresh_token
            existing.scope = scope
            existing.status = CONN_ACTIVE
            existing.error_message = None
            existing.account_name = account_name or existing.account_name
            existing.account_metadata = account_metadata
            db.commit()
            db.refresh(existing)
            return existing

        connection = PlatformConnection(
            organization_id=organization_id,
            user_id=user_id,
            platform=PLATFORM_STRIPE,
            account_id=stripe_user_id,
            account_name=account_name,
            account_metadata=account_metadata,
            access_token=access_token,
            refresh_token=refresh_token,
            scope=scope,
            status=CONN_ACTIVE,
        )
        db.add(connection)
        db.commit()
        db.refresh(connection)
        return connection

    @staticmethod
    def disconnect(
        db: Session,
        *,
        organization_id: int,
        connection_id: int,
    ) -> bool:
        """Revoke at Stripe (best-effort) and delete the row."""
        conn: Optional[PlatformConnection] = (
            db.query(PlatformConnection)
            .filter(
                PlatformConnection.id == connection_id,
                PlatformConnection.organization_id == organization_id,
            )
            .first()
        )
        if conn is None:
            return False

        if conn.platform == PLATFORM_STRIPE and settings.STRIPE_SECRET_KEY:
            try:
                stripe.api_key = settings.STRIPE_SECRET_KEY
                stripe.OAuth.deauthorize(
                    client_id=settings.STRIPE_CONNECT_CLIENT_ID,
                    stripe_user_id=conn.account_id,
                )
            except Exception:
                # The connection is being disconnected anyway — log only.
                pass

        db.delete(conn)
        db.commit()
        return True
