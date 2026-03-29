"""
Campaign Service

Business logic for campaign operations:
- Get user campaigns
- Get campaign details
- Get campaign metrics
- Calculate aggregates
"""

from sqlalchemy.orm import Session
from sqlalchemy import func
from typing import List, Optional
from datetime import date, timedelta

from app.models.campaign import Campaign
from app.models.metric import Metric


class CampaignService:
    """Service for campaign operations"""
    
    @staticmethod
    def get_user_campaigns(
        db: Session,
        user_id: int,
        platform: Optional[str] = None,
        status: Optional[str] = None,
        limit: int = 100,
        offset: int = 0
    ) -> tuple[List[Campaign], int]:
        """
        Get campaigns for a user with optional filters.
        
        Args:
            db: Database session
            user_id: User ID
            platform: Filter by platform (optional)
            status: Filter by status (optional)
            limit: Max results
            offset: Pagination offset
            
        Returns:
            Tuple of (campaigns list, total count)
        """
        query = db.query(Campaign).filter(Campaign.user_id == user_id)
        
        # Apply filters
        if platform:
            query = query.filter(Campaign.platform == platform)
        if status:
            query = query.filter(Campaign.status == status)
        
        # Get total count
        total = query.count()
        
        # Get paginated results
        campaigns = query.order_by(
            Campaign.last_synced_at.desc().nullslast(),
            Campaign.created_at.desc()
        ).limit(limit).offset(offset).all()
        
        return campaigns, total
    
    @staticmethod
    def get_campaign(
        db: Session,
        campaign_id: int,
        user_id: int
    ) -> Optional[Campaign]:
        """
        Get a single campaign (user must own it).
        
        Args:
            db: Database session
            campaign_id: Campaign ID
            user_id: User ID (for ownership check)
            
        Returns:
            Campaign if found and owned by user, None otherwise
        """
        return db.query(Campaign).filter(
            Campaign.id == campaign_id,
            Campaign.user_id == user_id
        ).first()
    
    @staticmethod
    def get_campaign_metrics(
        db: Session,
        campaign_id: int,
        user_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None,
        limit: int = 90
    ) -> tuple[List[Metric], dict]:
        """
        Get metrics for a campaign with aggregated summary.
        
        Args:
            db: Database session
            campaign_id: Campaign ID
            user_id: User ID (for ownership check)
            start_date: Filter from date (default: 30 days ago)
            end_date: Filter to date (default: today)
            limit: Max records
            
        Returns:
            Tuple of (metrics list, summary dict)
        """
        # Verify campaign ownership
        campaign = CampaignService.get_campaign(db, campaign_id, user_id)
        if not campaign:
            return [], {}
        
        # Default date range: last 30 days
        if not end_date:
            end_date = date.today()
        if not start_date:
            start_date = end_date - timedelta(days=30)
        
        # Get metrics
        query = db.query(Metric).filter(
            Metric.campaign_id == campaign_id,
            Metric.date >= start_date,
            Metric.date <= end_date
        )
        
        metrics = query.order_by(Metric.date.desc()).limit(limit).all()
        
        # Calculate summary
        summary = CampaignService._calculate_metrics_summary(metrics)
        
        return metrics, summary
    
    @staticmethod
    def _calculate_metrics_summary(metrics: List[Metric]) -> dict:
        """
        Calculate aggregated summary from metrics.
        
        Args:
            metrics: List of Metric objects
            
        Returns:
            Dict with aggregated stats
        """
        if not metrics:
            return {
                "total_impressions": 0,
                "total_clicks": 0,
                "total_cost": 0.0,
                "total_conversions": 0,
                "total_revenue": 0.0,
                "avg_ctr": 0.0,
                "avg_cpc": 0.0,
                "avg_cpa": None,
                "avg_cvr": 0.0,
                "avg_roi": None
            }
        
        # Sum totals
        total_impressions = sum(m.impressions for m in metrics)
        total_clicks = sum(m.clicks for m in metrics)
        total_cost = sum(m.cost for m in metrics)
        total_conversions = sum(m.conversions for m in metrics)
        total_revenue = sum(m.revenue or 0 for m in metrics)
        
        # Calculate averages
        avg_ctr = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0.0
        avg_cpc = (total_cost / total_clicks) if total_clicks > 0 else 0.0
        avg_cpa = (total_cost / total_conversions) if total_conversions > 0 else None
        avg_cvr = (total_conversions / total_clicks * 100) if total_clicks > 0 else 0.0
        avg_roi = ((total_revenue - total_cost) / total_cost * 100) if total_cost > 0 and total_revenue > 0 else None
        
        return {
            "total_impressions": total_impressions,
            "total_clicks": total_clicks,
            "total_cost": round(total_cost, 2),
            "total_conversions": total_conversions,
            "total_revenue": round(total_revenue, 2) if total_revenue > 0 else None,
            "avg_ctr": round(avg_ctr, 2),
            "avg_cpc": round(avg_cpc, 2),
            "avg_cpa": round(avg_cpa, 2) if avg_cpa else None,
            "avg_cvr": round(avg_cvr, 2),
            "avg_roi": round(avg_roi, 2) if avg_roi else None
        }