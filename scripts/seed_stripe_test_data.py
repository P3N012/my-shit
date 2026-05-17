"""
Populate a connected Stripe account with realistic test data.

Run AFTER you've completed the Connect OAuth flow at least once.
Reads the most recent active non-demo Stripe connection from the DB
(or takes one as `--account acct_xxx`) and pushes customers,
products, prices, and subscriptions into it via the Stripe API.

What it creates by default:
  - 3 products + prices: Starter ($29/mo), Pro ($99/mo), Business ($299/mo)
  - 30 customers, each attached to Stripe's universal test card
    (pm_card_visa) — the test card that always succeeds
  - 1 subscription per customer on a randomly chosen plan
  - ~5 of those subscriptions immediately canceled, so the dashboard
    has churn to show

All customers and subs live on the connected Stripe account, not in
your platform's data — they show up in your connected account's Stripe
dashboard, and they flow into the InsightPlus dashboard the next time
you click "Sync now".

Usage:
    python scripts/seed_stripe_test_data.py
    python scripts/seed_stripe_test_data.py --account acct_1XYZ --customers 50
"""

from __future__ import annotations

import argparse
import random
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import stripe

from app.core.config import settings
from app.core.database import SessionLocal
from app.models import (
    CONN_ACTIVE,
    PLATFORM_STRIPE,
    PlatformConnection,
)


PLANS = [
    {"name": "Starter",  "amount_cents": 2900,  "weight": 50},  # $29/mo
    {"name": "Pro",      "amount_cents": 9900,  "weight": 35},  # $99/mo
    {"name": "Business", "amount_cents": 29900, "weight": 15},  # $299/mo
]

COMPANY_PREFIXES = [
    "Acme", "Globex", "Initech", "Hooli", "Stark", "Wayne", "Wonka",
    "Tyrell", "Aperture", "Umbrella", "Pied Piper", "Pendant",
    "Vehement", "Anvil", "Bluth", "Sterling", "Goliath", "Nucleus",
]
COMPANY_SUFFIXES = [
    "Labs", "Inc", "Co", "Systems", "Group", "Ventures",
    "Cloud", "Networks", "Analytics", "Data", "Software",
]


def _random_company() -> str:
    return f"{random.choice(COMPANY_PREFIXES)} {random.choice(COMPANY_SUFFIXES)}"


def _random_email(name: str, i: int) -> str:
    domain = name.lower().replace(" ", "")
    return f"founder+{i}@{domain}.test"


def _weighted_plan() -> dict:
    return random.choices(PLANS, weights=[p["weight"] for p in PLANS], k=1)[0]


# ---------------------------------------------------------------------------
# Connection lookup
# ---------------------------------------------------------------------------

def _find_active_connection() -> str | None:
    """Most recent non-demo active Stripe connection, returned as account_id."""
    db = SessionLocal()
    try:
        row = (
            db.query(PlatformConnection)
            .filter(
                PlatformConnection.platform == PLATFORM_STRIPE,
                PlatformConnection.status == CONN_ACTIVE,
                ~PlatformConnection.account_id.like("acct_demo_%"),
            )
            .order_by(PlatformConnection.id.desc())
            .first()
        )
        return row.account_id if row else None
    finally:
        db.close()


# ---------------------------------------------------------------------------
# Stripe writes
# ---------------------------------------------------------------------------

def _create_products(account_id: str) -> list[tuple[str, str, int]]:
    """Returns [(plan_name, price_id, amount_cents), ...]."""
    out = []
    for plan in PLANS:
        product = stripe.Product.create(
            name=plan["name"],
            stripe_account=account_id,
        )
        price = stripe.Price.create(
            product=product.id,
            unit_amount=plan["amount_cents"],
            currency="usd",
            recurring={"interval": "month"},
            stripe_account=account_id,
        )
        out.append((plan["name"], price.id, plan["amount_cents"]))
    return out


def _create_customer_with_sub(
    account_id: str, name: str, email: str, price_id: str
):
    """Create a customer with a test card attached + a subscription on it.

    `pm_card_visa` is Stripe's universal test payment method that always
    succeeds in test mode. It's attached automatically when passed as the
    `payment_method` arg on customer creation.
    """
    customer = stripe.Customer.create(
        email=email,
        name=name,
        payment_method="pm_card_visa",
        invoice_settings={"default_payment_method": "pm_card_visa"},
        stripe_account=account_id,
    )
    subscription = stripe.Subscription.create(
        customer=customer.id,
        items=[{"price": price_id}],
        stripe_account=account_id,
    )
    return customer, subscription


def _cancel_subscription(account_id: str, subscription_id: str) -> None:
    stripe.Subscription.delete(subscription_id, stripe_account=account_id)


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main(account_id: str, num_customers: int, num_canceled: int) -> None:
    if not settings.STRIPE_SECRET_KEY:
        sys.exit(
            "STRIPE_SECRET_KEY is not configured. Set it in .env and try again."
        )
    stripe.api_key = settings.STRIPE_SECRET_KEY

    print(f"\nSeeding test data on connected account: {account_id}\n")

    print("Creating products + prices…")
    products = _create_products(account_id)
    for name, price_id, amount in products:
        print(f"  ✓ {name:10s} ${amount / 100:>6.2f}/mo  →  {price_id}")

    created_subs: list[tuple[str, str]] = []   # (subscription_id, customer_name)
    print(f"\nCreating {num_customers} customers + subscriptions…")
    for i in range(num_customers):
        name = _random_company()
        email = _random_email(name, i)
        plan_name, price_id, _amount = random.choices(
            products, weights=[p["weight"] for p in PLANS], k=1
        )[0]
        try:
            cust, sub = _create_customer_with_sub(account_id, name, email, price_id)
            created_subs.append((sub.id, name))
            print(f"  ✓ {name:30s} → {plan_name}")
        except stripe.error.StripeError as exc:
            print(f"  ✗ {name:30s} failed: {exc}")

    if num_canceled > 0 and created_subs:
        print(f"\nCanceling {num_canceled} subscriptions for churn data…")
        for sub_id, name in created_subs[:num_canceled]:
            try:
                _cancel_subscription(account_id, sub_id)
                print(f"  ✓ {name} canceled")
            except stripe.error.StripeError as exc:
                print(f"  ✗ {name} cancel failed: {exc}")

    print(
        "\nDone. In the app: go to Connections → click 'Sync now' on the "
        f"{account_id} card. The dashboard will populate after the sync."
    )


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "--account",
        help="Stripe connected account id (acct_...). "
        "If omitted, uses the most recent active Stripe connection from the DB.",
    )
    parser.add_argument(
        "--customers", type=int, default=30,
        help="How many customers to create (default 30).",
    )
    parser.add_argument(
        "--canceled", type=int, default=5,
        help="How many subscriptions to immediately cancel (default 5).",
    )
    parser.add_argument(
        "--seed", type=int, default=None,
        help="Random seed for reproducibility (default: time-based).",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = _parse_args()
    if args.seed is not None:
        random.seed(args.seed)

    account_id = args.account or _find_active_connection()
    if not account_id:
        sys.exit(
            "No active Stripe connection found. Connect one through the "
            "frontend first, or pass --account acct_xxx."
        )

    main(
        account_id=account_id,
        num_customers=args.customers,
        num_canceled=min(args.canceled, args.customers),
    )
