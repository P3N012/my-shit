"""
Seed database with test data

This script creates:
- Test users
- Platform connections (mock)
- Sample campaigns
- Sample metrics (30 days of data)
- Sample insights
"""

import sys
from pathlib import Path
from datetime import datetime, timedelta, date
import random

# Add parent directory to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from app.core.database import SessionLocal, init_db
from app.core.security import hash_password
from app.models import (
    User, RefreshToken, PlatformConnection, Campaign,
    Metric, SyncLog, Insight, ReportPreference
)


def create_test_users(db):
    """Create test users"""
    print("Creating test users...")
    
    users = [
        User(
            email="test@insightplus.com",
            username="testuser",
            password=hash_password("password123"),
            is_admin=False,
            is_client=True,
            status="active",
            subscription_tier="professional",
            subscription_status="active"
        ),
        User(
            email="admin@insightplus.com",
            username="admin",
            password=hash_password("admin123"),
            is_admin=True,
            is_client=False,
            status="active"
        ),
    ]
    
    for user in users:
        db.add(user)
    
    db.commit()
    
    # Refresh to get IDs
    for user in users:
        db.refresh(user)
    
    print(f"✅ Created {len(users)} test users")
    return users


def create_platform_connections(db, user):
    """Create mock platform connections"""
    print("Creating platform connections...")
    
    connections = [
        PlatformConnection(
            user_id=user.id,
            platform="google_ads",
            account_id="1234567890",
            account_name="Test Google Ads Account",
            access_token="mock_google_access_token",
            refresh_token="mock_google_refresh_token",
            status="active",
            last_sync_at=datetime.utcnow() - timedelta(hours=2),
            sync_status="success"
        ),
        PlatformConnection(
            user_id=user.id,
            platform="meta_ads",
            account_id="act_9876543210",
            account_name="Test Meta Ads Account",
            access_token="mock_meta_access_token",
            status="active",
            last_sync_at=datetime.utcnow() - timedelta(hours=3),
            sync_status="success"
        ),
    ]
    
    for conn in connections:
        db.add(conn)
    
    db.commit()
    
    # Refresh to get IDs
    for conn in connections:
        db.refresh(conn)
    
    print(f"✅ Created {len(connections)} platform connections")
    return connections


def create_campaigns(db, user, connections):
    """Create sample campaigns"""
    print("Creating campaigns...")
    
    google_conn = connections[0]
    meta_conn = connections[1]
    
    campaigns = [
        # Google Ads campaigns
        Campaign(
            user_id=user.id,
            connection_id=google_conn.id,
            platform_campaign_id="google_12345",
            name="Summer Sale 2026",
            platform="google_ads",
            status="active",
            start_date=date.today() - timedelta(days=30)
        ),
        Campaign(
            user_id=user.id,
            connection_id=google_conn.id,
            platform_campaign_id="google_12346",
            name="Brand Awareness",
            platform="google_ads",
            status="active",
            start_date=date.today() - timedelta(days=60)
        ),
        Campaign(
            user_id=user.id,
            connection_id=google_conn.id,
            platform_campaign_id="google_12347",
            name="Product Launch",
            platform="google_ads",
            status="paused",
            start_date=date.today() - timedelta(days=45)
        ),
        # Meta Ads campaigns
        Campaign(
            user_id=user.id,
            connection_id=meta_conn.id,
            platform_campaign_id="meta_67890",
            name="Facebook Retargeting",
            platform="meta_ads",
            status="active",
            start_date=date.today() - timedelta(days=30)
        ),
        Campaign(
            user_id=user.id,
            connection_id=meta_conn.id,
            platform_campaign_id="meta_67891",
            name="Instagram Stories",
            platform="meta_ads",
            status="active",
            start_date=date.today() - timedelta(days=20)
        ),
    ]
    
    for campaign in campaigns:
        db.add(campaign)
    
    db.commit()
    
    # Refresh to get IDs
    for campaign in campaigns:
        db.refresh(campaign)
    
    print(f"✅ Created {len(campaigns)} campaigns")
    return campaigns


def create_metrics(db, campaigns):
    """Create 30 days of metrics for each campaign"""
    print("Creating metrics (30 days for each campaign)...")
    
    metrics_count = 0
    
    for campaign in campaigns:
        # Generate 30 days of data
        for i in range(30):
            metric_date = date.today() - timedelta(days=30-i)
            
            # Realistic ranges based on platform
            if campaign.platform == "google_ads":
                base_impressions = random.randint(5000, 15000)
                base_cost = random.uniform(100, 500)
            else:  # meta_ads
                base_impressions = random.randint(3000, 10000)
                base_cost = random.uniform(80, 400)
            
            clicks = int(base_impressions * random.uniform(0.02, 0.08))  # 2-8% CTR
            conversions = int(clicks * random.uniform(0.02, 0.10))  # 2-10% CVR
            revenue = conversions * random.uniform(50, 200) if conversions > 0 else 0
            
            metric = Metric(
                campaign_id=campaign.id,
                date=metric_date,
                impressions=base_impressions,
                clicks=clicks,
                conversions=conversions,
                cost=round(base_cost, 2),
                revenue=round(revenue, 2) if revenue > 0 else None,
                currency="USD"
            )
            
            db.add(metric)
            metrics_count += 1
    
    db.commit()
    print(f"✅ Created {metrics_count} metric records")


def create_sync_logs(db, connections):
    """Create sample sync logs"""
    print("Creating sync logs...")
    
    logs = []
    for conn in connections:
        # Last successful sync
        log = SyncLog(
            connection_id=conn.id,
            started_at=datetime.utcnow() - timedelta(hours=2),
            completed_at=datetime.utcnow() - timedelta(hours=2, minutes=-5),
            status="success",
            campaigns_fetched=3 if conn.platform == "google_ads" else 2,
            campaigns_updated=3 if conn.platform == "google_ads" else 2,
            metrics_created=90 if conn.platform == "google_ads" else 60,
            triggered_by="automatic"
        )
        logs.append(log)
        db.add(log)
    
    db.commit()
    print(f"✅ Created {len(logs)} sync logs")


def create_insights(db, user, campaigns):
    """Create sample insights"""
    print("Creating insights...")
    
    insights = [
        Insight(
            user_id=user.id,
            type="performance_trend",
            severity="negative",
            message="Campaign 'Summer Sale 2026' ROI dropped 28% this week",
            detail="Possible causes: CPC increased 15%, conversions down 18%",
            related_campaigns=[campaigns[0].id],
            data={"change_pct": -28, "metric": "roi"}
        ),
        Insight(
            user_id=user.id,
            type="platform_comparison",
            severity="positive",
            message="Meta campaigns 35% more efficient than Google Ads",
            detail="Meta ROI: 4.2x | Google ROI: 2.8x",
            related_platforms=["google_ads", "meta_ads"],
            data={"meta_roi": 4.2, "google_roi": 2.8, "diff_pct": 35}
        ),
        Insight(
            user_id=user.id,
            type="underperforming_campaign",
            severity="caution",
            message="Campaign 'Product Launch' underperforming",
            detail="ROI: 1.2x (account avg: 3.5x)",
            related_campaigns=[campaigns[2].id],
            data={"campaign_roi": 1.2, "avg_roi": 3.5}
        ),
    ]
    
    for insight in insights:
        db.add(insight)
    
    db.commit()
    print(f"✅ Created {len(insights)} insights")


def create_report_preference(db, user):
    """Create report preference"""
    print("Creating report preference...")
    
    pref = ReportPreference(
        user_id=user.id,
        enabled=True,
        frequency="weekly",
        day_of_week=1,  # Monday
        time="09:00",
        timezone="America/New_York",
        include_overview=True,
        include_platform_breakdown=True,
        include_top_campaigns=True,
        include_insights=True,
        date_range_days=7
    )
    
    db.add(pref)
    db.commit()
    print("✅ Created report preference")


def main():
    """Main seed function"""
    print("\n" + "="*50)
    print("🌱 SEEDING DATABASE WITH TEST DATA")
    print("="*50 + "\n")
    
    # Initialize database (create tables if not exist)
    print("Initializing database...")
    init_db()
    print()
    
    # Create session
    db = SessionLocal()
    
    try:
        # Check if data already exists
        existing_users = db.query(User).count()
        if existing_users > 0:
            print("⚠️  Database already has data!")
            response = input("Do you want to continue? This will add more test data. (y/n): ")
            if response.lower() != 'y':
                print("❌ Seeding cancelled")
                return
            print()
        
        # Create test data
        users = create_test_users(db)
        test_user = users[0]  # Use first user for sample data
        
        connections = create_platform_connections(db, test_user)
        campaigns = create_campaigns(db, test_user, connections)
        create_metrics(db, campaigns)
        create_sync_logs(db, connections)
        create_insights(db, test_user, campaigns)
        create_report_preference(db, test_user)
        
        print("\n" + "="*50)
        print("✅ DATABASE SEEDED SUCCESSFULLY!")
        print("="*50)
        print("\n📋 Test Credentials:")
        print("   Email: test@insightplus.com")
        print("   Password: password123")
        print("\n   Admin Email: admin@insightplus.com")
        print("   Admin Password: admin123")
        print()
        
    except Exception as e:
        print(f"\n❌ Error seeding database: {e}")
        import traceback
        traceback.print_exc()
        db.rollback()
        raise
    finally:
        db.close()


if __name__ == "__main__":
    main()