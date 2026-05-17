"""
Generate a year of synthetic Stripe data for each seeded test user.

Each user's first org gets a demo PlatformConnection (status=active,
account_id="acct_demo_*"), plus:

- ~150 customers spread across the past 12 months
- A subscription per customer on one of three plans
- ~10% of customers have churned (canceled_at set)
- A few high-value customers (upgrades, anomalies)
- Monthly charges per active subscription for the past 90 days
- A few failed charges (for the AI to notice)

Idempotent — re-running deletes the existing demo data for the user's
org first, then re-seeds. Real connections (account_id not starting
with `acct_demo_`) are left alone.

Run with:
    python scripts/seed_demo_data.py
"""

import random
import sys
import uuid
from datetime import datetime, timedelta, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from app.core.database import SessionLocal
from app.models import (
    CONN_ACTIVE,
    PLATFORM_STRIPE,
    PlatformConnection,
    StripeCharge,
    StripeCustomer,
    StripeSubscription,
    User,
)


# ---------------------------------------------------------------------------
# Tunables
# ---------------------------------------------------------------------------

PLANS = [
    {"name": "Starter",    "amount_cents": 2900,  "weight": 50},  # $29/mo
    {"name": "Pro",        "amount_cents": 9900,  "weight": 30},  # $99/mo
    {"name": "Business",   "amount_cents": 29900, "weight": 15},  # $299/mo
    {"name": "Enterprise", "amount_cents": 99900, "weight": 5},   # $999/mo
]

TOTAL_CUSTOMERS = 160        # spread across the past 12 months
CHURN_RATIO = 0.10           # ~10% have canceled at some point
PAST_DUE_RATIO = 0.03        # ~3% currently past_due
CHARGE_WINDOW_DAYS = 90      # how far back to generate charges
FAILED_CHARGE_RATE = 0.04    # ~4% of generated charges are "failed"


COMPANY_PREFIXES = [
    "Acme", "Globex", "Initech", "Hooli", "Pied Piper", "Stark",
    "Wayne", "Wonka", "Massive Dynamic", "Cyberdyne", "Tyrell",
    "Aperture", "Black Mesa", "Umbrella", "Soylent", "OsCorp",
    "Vandelay", "Bluth", "Sterling Cooper", "Dunder Mifflin",
    "Vehement", "Spade", "Ollivanders", "Nakatomi", "Volkov",
    "Pendant", "Pearson", "Goliath", "Nucleus", "Anvil",
]
COMPANY_SUFFIXES = [
    "Labs", "Inc", "Co", "Systems", "Studios", "Group", "Holdings",
    "Industries", "Partners", "Ventures", "Cloud", "Networks",
    "Robotics", "Analytics", "Data", "Software", "Logistics",
]


def _utcnow() -> datetime:
    return datetime.now(timezone.utc)


def _random_company() -> str:
    return f"{random.choice(COMPANY_PREFIXES)} {random.choice(COMPANY_SUFFIXES)}"


def _random_email(name: str) -> str:
    domain = name.lower().replace(" ", "")
    user = random.choice(["billing", "ops", "founder", "finance", "hello"])
    return f"{user}@{domain}.test"


def _stripe_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:20]}"


def _weighted_choice():
    return random.choices(
        PLANS, weights=[p["weight"] for p in PLANS], k=1
    )[0]


# ---------------------------------------------------------------------------
# Per-org seeding
# ---------------------------------------------------------------------------

def _clear_demo_data(db, connection_id: int) -> None:
    """Wipe the rows under a demo connection so the run is idempotent."""
    db.query(StripeCharge).filter(StripeCharge.connection_id == connection_id).delete()
    db.query(StripeSubscription).filter(
        StripeSubscription.connection_id == connection_id
    ).delete()
    db.query(StripeCustomer).filter(
        StripeCustomer.connection_id == connection_id
    ).delete()
    db.commit()


def _ensure_demo_connection(db, *, organization_id: int, user_id: int) -> PlatformConnection:
    """Find or create the demo connection for this org."""
    existing = (
        db.query(PlatformConnection)
        .filter(
            PlatformConnection.organization_id == organization_id,
            PlatformConnection.platform == PLATFORM_STRIPE,
            PlatformConnection.account_id.like("acct_demo_%"),
        )
        .first()
    )
    if existing:
        return existing

    conn = PlatformConnection(
        organization_id=organization_id,
        user_id=user_id,
        platform=PLATFORM_STRIPE,
        account_id=_stripe_id("acct_demo"),
        account_name="Demo Account",
        account_metadata={"livemode": False, "demo": True},
        access_token="demo_no_real_token",
        refresh_token=None,
        scope="read_only",
        status=CONN_ACTIVE,
        last_synced_at=_utcnow(),
        last_sync_status="success",
    )
    db.add(conn)
    db.commit()
    db.refresh(conn)
    return conn


def _seed_org(db, *, organization_id: int, user_id: int) -> None:
    conn = _ensure_demo_connection(db, organization_id=organization_id, user_id=user_id)
    _clear_demo_data(db, conn.id)

    now = _utcnow()
    one_year_ago = now - timedelta(days=365)

    # Decide upfront which customers will churn and when.
    customer_ids = list(range(TOTAL_CUSTOMERS))
    random.shuffle(customer_ids)
    churn_count = int(TOTAL_CUSTOMERS * CHURN_RATIO)
    churned_set = set(customer_ids[:churn_count])
    past_due_count = int(TOTAL_CUSTOMERS * PAST_DUE_RATIO)
    past_due_set = set(customer_ids[churn_count : churn_count + past_due_count])

    customers: list[StripeCustomer] = []
    subscriptions: list[StripeSubscription] = []
    charges: list[StripeCharge] = []

    for i in range(TOTAL_CUSTOMERS):
        # Random creation date across the past year, weighted toward more
        # recent (so growth looks like an actual ramp).
        weight = random.random() ** 0.5  # bias toward newer
        created_at = one_year_ago + timedelta(seconds=int(weight * 365 * 86400))
        name = _random_company()
        email = _random_email(name)

        cust_id = _stripe_id("cus")
        customer = StripeCustomer(
            connection_id=conn.id,
            stripe_customer_id=cust_id,
            email=email,
            name=name,
            currency="usd",
            balance=0,
            delinquent=i in past_due_set,
            livemode=False,
            stripe_metadata={},
            stripe_created_at=created_at,
            synced_at=now,
        )
        customers.append(customer)

        plan = _weighted_choice()
        # Small chance of annual billing on the big plans (Business + Enterprise).
        is_annual = plan["amount_cents"] >= 29900 and random.random() < 0.3
        interval = "year" if is_annual else "month"
        amount_per_period = plan["amount_cents"] * 12 if is_annual else plan["amount_cents"]

        sub_id = _stripe_id("sub")
        if i in churned_set:
            # Cancel somewhere between halfway through their tenure and
            # a day before "now". The half-tenure floor makes sure even
            # young customers (< 30 days old) can churn cleanly without
            # the prior bug where the floor (30d) overshot the ceiling.
            age_seconds = int((now - created_at).total_seconds())
            half = max(1, age_seconds // 2)
            canceled_seconds = random.randint(half, max(half, age_seconds - 86400))
            canceled_at = created_at + timedelta(seconds=canceled_seconds)
            status = "canceled"
            ended_at = canceled_at
        elif i in past_due_set:
            canceled_at = None
            ended_at = None
            status = "past_due"
        else:
            canceled_at = None
            ended_at = None
            status = "active"

        period_seconds = 365 * 86400 if is_annual else 30 * 86400
        period_end = created_at + timedelta(seconds=period_seconds)
        while period_end < now and status not in ("canceled",):
            period_end += timedelta(seconds=period_seconds)

        subscription = StripeSubscription(
            connection_id=conn.id,
            stripe_subscription_id=sub_id,
            stripe_customer_id=cust_id,
            status=status,
            currency="usd",
            amount_per_period=amount_per_period,
            interval=interval,
            interval_count=1,
            current_period_start=period_end - timedelta(seconds=period_seconds),
            current_period_end=period_end,
            cancel_at_period_end=False,
            canceled_at=canceled_at,
            started_at=created_at,
            ended_at=ended_at,
            trial_end=None,
            items_json=[
                {
                    "id": _stripe_id("si"),
                    "price_id": f"price_demo_{plan['name'].lower()}",
                    "unit_amount": amount_per_period,
                    "quantity": 1,
                }
            ],
            stripe_metadata={"plan": plan["name"]},
            stripe_created_at=created_at,
            synced_at=now,
        )
        subscriptions.append(subscription)

        # Charges: monthly cadence for active subs, in the last CHARGE_WINDOW_DAYS.
        charge_start = max(created_at, now - timedelta(days=CHARGE_WINDOW_DAYS))
        if canceled_at and canceled_at < charge_start:
            continue
        cursor = charge_start
        monthly_amount = plan["amount_cents"] if not is_annual else 0  # annual subs bill once
        if is_annual:
            # If the annual renewal happens in the window, generate that charge.
            renewal = created_at
            while renewal < now:
                if renewal >= charge_start and (not canceled_at or renewal < canceled_at):
                    charges.append(
                        _build_charge(conn.id, cust_id, amount_per_period, renewal, now)
                    )
                renewal += timedelta(days=365)
        else:
            # Pick a stable "billing day" for this customer.
            billing_day_offset = (created_at.day - 1) % 28
            cursor = charge_start.replace(day=1) + timedelta(days=billing_day_offset)
            while cursor < now:
                if cursor >= charge_start and (not canceled_at or cursor < canceled_at):
                    charges.append(
                        _build_charge(conn.id, cust_id, monthly_amount, cursor, now)
                    )
                cursor += timedelta(days=30)

    db.add_all(customers)
    db.add_all(subscriptions)
    db.add_all(charges)
    db.commit()

    print(
        f"  → org {organization_id}: "
        f"{len(customers)} customers, {len(subscriptions)} subs, {len(charges)} charges"
    )


def _build_charge(
    connection_id: int, customer_id: str, amount_cents: int, at: datetime, now: datetime
) -> StripeCharge:
    failed = random.random() < FAILED_CHARGE_RATE
    return StripeCharge(
        connection_id=connection_id,
        stripe_charge_id=_stripe_id("ch"),
        stripe_customer_id=customer_id,
        amount=amount_cents,
        amount_refunded=0,
        currency="usd",
        status="failed" if failed else "succeeded",
        paid=not failed,
        refunded=False,
        livemode=False,
        description=None,
        failure_code="card_declined" if failed else None,
        failure_message="Your card was declined." if failed else None,
        stripe_metadata={},
        stripe_created_at=at,
        synced_at=now,
    )


# ---------------------------------------------------------------------------
# Entry point
# ---------------------------------------------------------------------------

def main() -> None:
    print("\n" + "=" * 50)
    print("SEEDING DEMO STRIPE DATA")
    print("=" * 50)
    print("Run `python scripts/seed_db.py` first if you haven't seeded users.\n")

    random.seed(42)  # deterministic data so the AI review is reproducible

    db = SessionLocal()
    try:
        users = db.query(User).all()
        if not users:
            print("No users found. Run scripts/seed_db.py first.")
            return

        for user in users:
            if not user.memberships:
                continue
            primary_org_id = user.memberships[0].organization_id
            print(f"Seeding for user '{user.username}' (org {primary_org_id})…")
            _seed_org(db, organization_id=primary_org_id, user_id=user.id)

        print("\nDone. Log in and visit /dashboard to see the numbers.")
    finally:
        db.close()


if __name__ == "__main__":
    main()
