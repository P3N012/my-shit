"""
Seed database with test data

This script creates:
- Test users
"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import SessionLocal
from app.core.security import hash_password
from app.models import ROLE_OWNER, Membership, Organization, User


def create_test_users(db):
    """Create test users"""
    print("Creating test users...")

    users = [
        User(
            email="test@insightplus.com",
            username="testuser",
            password_hash=hash_password("password123"),
            is_admin=False,
            is_client=True,
            status="active",
            subscription_tier="professional",
            subscription_status="active",
        ),
        User(
            email="admin@insightplus.com",
            username="admin",
            password_hash=hash_password("admin123"),
            is_admin=True,
            is_client=False,
            status="active",
        ),
    ]

    for user in users:
        db.add(user)
    db.flush()

    for user in users:
        org = Organization(name=f"{user.username}'s workspace")
        db.add(org)
        db.flush()
        db.add(
            Membership(
                user_id=user.id, organization_id=org.id, role=ROLE_OWNER
            )
        )

    db.commit()

    for user in users:
        db.refresh(user)

    print(f"Created {len(users)} test users (each with a personal org)")
    return users


def main():
    print("\n" + "=" * 50)
    print("SEEDING DATABASE WITH TEST DATA")
    print("=" * 50 + "\n")
    print("Run `alembic upgrade head` first if you haven't.\n")

    db = SessionLocal()

    try:
        existing_users = db.query(User).count()
        if existing_users > 0:
            print("Database already has data.")
            response = input("Continue and add more test users? (y/n): ")
            if response.lower() != 'y':
                print("Seeding cancelled")
                return
            print()

        create_test_users(db)

        print("\n" + "=" * 50)
        print("DATABASE SEEDED SUCCESSFULLY")
        print("=" * 50)
        print("\nTest Credentials:")
        print("   Email: test@insightplus.com")
        print("   Password: password123")
        print("\n   Admin Email: admin@insightplus.com")
        print("   Admin Password: admin123")
        print()

    except Exception as e:
        print(f"\nError seeding database: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()
