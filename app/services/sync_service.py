"""
Sync Service

Business logic for syncing platform data:
- Fetch campaigns from Google Ads
- Fetch metrics
- Store in database
- Handle errors and logging
"""

from sqlalchemy.orm import Session
from datetime import datetime, timedelta, date
from typing import Optional

from app.models.platform_connection import PlatformConnection
from app.models.campaign import Campaign
from app.models.metric import Metric
from app.models.sync_log import SyncLog
from app.services.google_ads_service import GoogleAdsService
from app.services.oauth_service import OAuthService
from app.core.config import settings


class SyncService:
    """Service for syncing platform data"""
    
    @staticmethod
    def sync_google_ads(
        db: Session,
        connection: PlatformConnection
    ) -> SyncLog:
        """
        Sync Google Ads campaigns and metrics.
        
        Args:
            db: Database session
            connection: PlatformConnection object
            
        Returns:
            SyncLog object with sync results
        """
        # Create sync log
        sync_log = SyncLog(
            connection_id=connection.id,
            started_at=datetime.utcnow(),
            status="in_progress",
            triggered_by="manual"
        )
        db.add(sync_log)
        db.commit()
        db.refresh(sync_log)
        
        try:
            # Refresh token if needed
            OAuthService.refresh_google_ads_token(db, connection)
            
            # Create Google Ads client
            client = GoogleAdsService.create_client(
                developer_token=settings.GOOGLE_ADS_DEVELOPER_TOKEN,
                client_id=settings.GOOGLE_ADS_CLIENT_ID,
                client_secret=settings.GOOGLE_ADS_CLIENT_SECRET,
                refresh_token=connection.refresh_token,
                login_customer_id=connection.account_id if connection.account_id != "pending" else None
            )
            
            # Get customer info if account_id is pending
            if connection.account_id == "pending":
                # For now, we'll need the user to provide customer_id
                # In production, you'd list accessible customers
                sync_log.error_message = "Customer ID not set. Please update connection with valid customer_id."
                sync_log.status = "failed"
                sync_log.completed_at = datetime.utcnow()
                db.commit()
                return sync_log
            
            customer_id = connection.account_id
            
            # Fetch campaigns
            try:
                campaigns_data = GoogleAdsService.fetch_campaigns(client, customer_id)
            except Exception as campaign_error:
                # Better error handling for Google Ads API errors
                error_msg = str(campaign_error)
                if hasattr(campaign_error, 'error'):
                    error_msg = f"Google Ads API Error: {campaign_error.error}"
                elif hasattr(campaign_error, 'details'):
                    error_msg = f"API Error: {campaign_error.details()}"
                
                sync_log.error_message = error_msg
                sync_log.status = "failed"
                sync_log.completed_at = datetime.utcnow()
                connection.sync_status = "failed"
                connection.error_message = error_msg
                connection.consecutive_failures += 1
                db.commit()
                raise Exception(error_msg)
            
            campaigns_created = 0
            campaigns_updated = 0
            
            for campaign_data in campaigns_data:
                # Check if campaign exists
                existing = db.query(Campaign).filter(
                    Campaign.connection_id == connection.id,
                    Campaign.platform_campaign_id == campaign_data["platform_campaign_id"]
                ).first()
                
                if existing:
                    # Update existing campaign
                    existing.name = campaign_data["name"]
                    existing.status = campaign_data["status"]
                    existing.last_synced_at = datetime.utcnow()
                    campaigns_updated += 1
                else:
                    # Create new campaign
                    campaign = Campaign(
                        user_id=connection.user_id,
                        connection_id=connection.id,
                        platform_campaign_id=campaign_data["platform_campaign_id"],
                        name=campaign_data["name"],
                        platform="google_ads",
                        status=campaign_data["status"],
                        last_synced_at=datetime.utcnow()
                    )
                    db.add(campaign)
                    campaigns_created += 1
            
            db.commit()
            
            # Fetch metrics for last 30 days
            end_date = date.today()
            start_date = end_date - timedelta(days=30)
            
            metrics_data = GoogleAdsService.fetch_campaign_metrics(
                client,
                customer_id,
                start_date,
                end_date
            )
            
            metrics_created = 0
            metrics_updated = 0
            
            for metric_data in metrics_data:
                # Get campaign by platform_campaign_id
                campaign = db.query(Campaign).filter(
                    Campaign.connection_id == connection.id,
                    Campaign.platform_campaign_id == metric_data["platform_campaign_id"]
                ).first()
                
                if not campaign:
                    continue  # Skip if campaign not found
                
                # Check if metric exists
                existing_metric = db.query(Metric).filter(
                    Metric.campaign_id == campaign.id,
                    Metric.date == metric_data["date"]
                ).first()
                
                if existing_metric:
                    # Update existing metric
                    existing_metric.impressions = metric_data["impressions"]
                    existing_metric.clicks = metric_data["clicks"]
                    existing_metric.cost = metric_data["cost"]
                    existing_metric.conversions = metric_data["conversions"]
                    existing_metric.revenue = metric_data.get("revenue")
                    metrics_updated += 1
                else:
                    # Create new metric
                    metric = Metric(
                        campaign_id=campaign.id,
                        date=metric_data["date"],
                        impressions=metric_data["impressions"],
                        clicks=metric_data["clicks"],
                        cost=metric_data["cost"],
                        conversions=metric_data["conversions"],
                        revenue=metric_data.get("revenue")
                    )
                    db.add(metric)
                    metrics_created += 1
            
            db.commit()
            
            # Update sync log
            sync_log.status = "success"
            sync_log.campaigns_fetched = len(campaigns_data)
            sync_log.campaigns_created = campaigns_created
            sync_log.campaigns_updated = campaigns_updated
            sync_log.metrics_created = metrics_created
            sync_log.metrics_updated = metrics_updated
            sync_log.completed_at = datetime.utcnow()
            
            # Update connection
            connection.last_sync_at = datetime.utcnow()
            connection.sync_status = "success"
            connection.error_message = None
            connection.consecutive_failures = 0
            
            db.commit()
            db.refresh(sync_log)
            
            return sync_log
            
        except Exception as e:
            # Log error
            sync_log.status = "failed"
            sync_log.error_message = str(e)
            sync_log.completed_at = datetime.utcnow()
            
            # Update connection
            connection.sync_status = "failed"
            connection.error_message = str(e)
            connection.consecutive_failures += 1
            
            db.commit()
            db.refresh(sync_log)
            
            raise
    
    @staticmethod
    def get_sync_logs(
        db: Session,
        connection_id: int,
        limit: int = 10
    ) -> list[SyncLog]:
        """
        Get sync logs for a connection.
        
        Args:
            db: Database session
            connection_id: Connection ID
            limit: Maximum number of logs to return
            
        Returns:
            List of SyncLog objects
        """
        return db.query(SyncLog).filter(
            SyncLog.connection_id == connection_id
        ).order_by(
            SyncLog.started_at.desc()
        ).limit(limit).all()