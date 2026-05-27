"""
Connect a Stripe account with a read-only restricted API key.

This is the trust-first alternative to OAuth: the user creates a
**restricted key** (`rk_…`) in their own Stripe dashboard, grants it
read-only access to exactly the resources we need (Customers,
Subscriptions, Charges), and pastes it in. They control the scope and
can revoke the key any time — InsightPlus never gets write access and
never sees their Stripe password.

We refuse full secret keys (`sk_…`): if someone pastes one we reject it
and tell them to create a restricted key instead.
"""

from __future__ import annotations

import hashlib
from typing import Optional

import stripe
from sqlalchemy.orm import Session

from app.models.platform_connection import (
    AUTH_RESTRICTED_KEY,
    CONN_ACTIVE,
    PLATFORM_STRIPE,
    PlatformConnection,
)

RESTRICTED_KEY_PREFIXES = ("rk_live_", "rk_test_")
SECRET_KEY_PREFIXES = ("sk_live_", "sk_test_")


class StripeApiKeyService:
    @staticmethod
    def connect(
        db: Session,
        *,
        user_id: int,
        organization_id: int,
        api_key: str,
    ) -> PlatformConnection:
        """
        Validate a restricted key and persist a PlatformConnection.

        Raises ValueError for any user-visible problem (wrong key type,
        invalid key, insufficient permissions). The route surfaces the
        message.
        """
        api_key = (api_key or "").strip()

        if api_key.startswith(SECRET_KEY_PREFIXES):
            raise ValueError(
                "That's a full secret key. Please create a read-only "
                "restricted key (rk_…) instead — it limits what we can access."
            )
        if not api_key.startswith(RESTRICTED_KEY_PREFIXES):
            raise ValueError(
                "That doesn't look like a Stripe restricted key. It should "
                "start with rk_live_ or rk_test_."
            )

        # Validate the key and learn which account it belongs to. Account
        # read may not be granted on a minimal key, so fall back to a
        # cheap Customers read to confirm the key works at all.
        account_id, account_name, livemode = StripeApiKeyService._identify(api_key)

        existing: Optional[PlatformConnection] = (
            db.query(PlatformConnection)
            .filter(
                PlatformConnection.organization_id == organization_id,
                PlatformConnection.platform == PLATFORM_STRIPE,
                PlatformConnection.account_id == account_id,
            )
            .first()
        )
        metadata = {"livemode": livemode, "auth_method": AUTH_RESTRICTED_KEY}
        if existing:
            existing.auth_method = AUTH_RESTRICTED_KEY
            existing.access_token = api_key
            existing.refresh_token = None
            existing.scope = "read_only"
            existing.status = CONN_ACTIVE
            existing.error_message = None
            existing.account_name = account_name or existing.account_name
            existing.account_metadata = metadata
            db.commit()
            db.refresh(existing)
            return existing

        connection = PlatformConnection(
            organization_id=organization_id,
            user_id=user_id,
            platform=PLATFORM_STRIPE,
            auth_method=AUTH_RESTRICTED_KEY,
            account_id=account_id,
            account_name=account_name,
            account_metadata=metadata,
            access_token=api_key,
            refresh_token=None,
            scope="read_only",
            status=CONN_ACTIVE,
        )
        db.add(connection)
        db.commit()
        db.refresh(connection)
        return connection

    @staticmethod
    def _identify(api_key: str) -> tuple[str, Optional[str], bool]:
        """
        Return (account_id, account_name, livemode) for a restricted key.

        Tries Account.retrieve first; if the key lacks Account read, falls
        back to a Customers read to prove the key is valid and synthesises
        a stable account id from the key so re-connecting updates the same
        row.
        """
        stripe.api_key = api_key
        try:
            account = stripe.Account.retrieve()
            name = (
                account.get("business_profile", {}).get("name")
                or account.get("settings", {}).get("dashboard", {}).get("display_name")
                or account.get("email")
            )
            return account["id"], name, bool(account.get("livemode", False))
        except stripe.error.PermissionError:
            # Key valid but no Account read — prove it works on Customers.
            try:
                stripe.Customer.list(limit=1)
            except stripe.error.StripeError as exc:
                raise ValueError(f"Stripe rejected the key: {exc.user_message or exc}")
            digest = hashlib.sha256(api_key.encode()).hexdigest()[:16]
            livemode = api_key.startswith("rk_live_")
            return f"acct_rk_{digest}", None, livemode
        except stripe.error.AuthenticationError:
            raise ValueError("That key is invalid or has been revoked.")
        except stripe.error.StripeError as exc:
            raise ValueError(f"Stripe rejected the key: {exc.user_message or exc}")
