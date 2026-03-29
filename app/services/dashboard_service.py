"""
Dashboard Service

Business logic for dashboard analytics:
- Calculate overall stats
- Platform comparison
- Top campaigns
- Insights summary
"""

from sqlalchemy.orm import Session
from sqlalchemy import func, and_
from datetime import date, timedelta
from typing import Optional, Dict, Any, List
from collections import defaultdict
from app.models.campaign import Campaign
from app.models.metric import Metric


class DashboardService:
    @staticmethod
    def get_overview(
        db: Session,
        user_id: int,
        start_date: Optional[date] = None,
        end_date: Optional[date] = None
    ) -> Dict[str, Any]:
        """
        Get complete dashboard overview matching DashboardOverviewResponse schema
        """
        
        # Set default date range (last 30 days)
        if not end_date:
            end_date = date.today()
        if not start_date:
            start_date = end_date - timedelta(days=30)
        
        # Query all campaigns for this user
        campaigns = db.query(Campaign).filter(
            Campaign.user_id == user_id
        ).all()
        
        if not campaigns:
            return DashboardService._empty_dashboard(start_date, end_date)
        
        campaign_ids = [c.id for c in campaigns]
        
        # Query metrics within date range
        metrics = db.query(Metric).filter(
            and_(
                Metric.campaign_id.in_(campaign_ids),
                Metric.date >= start_date,
                Metric.date <= end_date
            )
        ).all()
        
        if not metrics:
            return DashboardService._empty_dashboard(start_date, end_date)
        
        # Calculate overall stats
        overall_stats = DashboardService._calculate_overall_stats(metrics)
        
        # Calculate platform stats
        platform_stats = DashboardService._calculate_platform_stats(db, campaigns, metrics)
        
        # Get top campaigns
        top_campaigns = DashboardService._get_top_campaigns(
            db, campaign_ids, start_date, end_date, limit=5
        )
        
        # Count connected platforms (unique platforms with campaigns)
        connected_platforms = len(set(c.platform for c in campaigns if c.platform))
        
        # Calculate active insights count
        active_insights_count = 0
        
        # Insight 1: Check for low performers
        low_roi_campaigns = [c for c in top_campaigns if c.get('roi') and c['roi'] < 100]
        if low_roi_campaigns:
            active_insights_count += 1
        
        # Insight 2: Check platform performance difference
        if len(platform_stats) >= 2:
            platform_rois = [p['roi'] for p in platform_stats if p.get('roi')]
            if platform_rois and max(platform_rois) > min(platform_rois) * 1.2:
                active_insights_count += 1
        
        # Insight 3: Check for high performers to scale
        if top_campaigns and top_campaigns[0].get('roi') and top_campaigns[0]['roi'] > 200:
            active_insights_count += 1
        
        return {
            "start_date": start_date,
            "end_date": end_date,
            **overall_stats,
            "platforms": platform_stats,
            "top_campaigns": top_campaigns,
            "active_insights_count": active_insights_count,
            "total_campaigns": len(campaigns),
            "connected_platforms": connected_platforms
        }
    
    @staticmethod
    def _calculate_overall_stats(metrics: List[Metric]) -> Dict[str, Any]:
        """Calculate overall aggregated stats"""
        if not metrics:
            return {
                "total_impressions": 0,
                "total_clicks": 0,
                "total_cost": 0.0,
                "total_conversions": 0,
                "total_revenue": None,
                "overall_ctr": 0.0,
                "overall_cpc": 0.0,
                "overall_cpa": None,
                "overall_roi": None
            }
        
        total_impressions = sum(m.impressions or 0 for m in metrics)
        total_clicks = sum(m.clicks or 0 for m in metrics)
        total_cost = sum(m.cost or 0 for m in metrics)
        total_conversions = sum(m.conversions or 0 for m in metrics)
        total_revenue = sum(m.revenue or 0 for m in metrics)
        
        overall_ctr = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0.0
        overall_cpc = (total_cost / total_clicks) if total_clicks > 0 else 0.0
        overall_cpa = (total_cost / total_conversions) if total_conversions > 0 else None
        overall_roi = ((total_revenue - total_cost) / total_cost * 100) if total_cost > 0 and total_revenue > 0 else None
        
        return {
            "total_impressions": int(total_impressions),
            "total_clicks": int(total_clicks),
            "total_cost": round(total_cost, 2),
            "total_conversions": int(total_conversions),
            "total_revenue": round(total_revenue, 2) if total_revenue > 0 else None,
            "overall_ctr": round(overall_ctr, 2),
            "overall_cpc": round(overall_cpc, 2),
            "overall_cpa": round(overall_cpa, 2) if overall_cpa else None,
            "overall_roi": round(overall_roi, 2) if overall_roi else None
        }
    
    @staticmethod
    def _calculate_platform_stats(
        db: Session, 
        campaigns: List[Campaign], 
        metrics: List[Metric]
    ) -> List[Dict[str, Any]]:
        """Calculate stats per platform"""
        # Group campaigns by platform
        campaigns_by_platform = defaultdict(list)
        for campaign in campaigns:
            platform = campaign.platform or "unknown"
            campaigns_by_platform[platform].append(campaign.id)
        
        # Group metrics by platform
        metrics_by_platform = defaultdict(list)
        campaign_platform_map = {c.id: c.platform or "unknown" for c in campaigns}
        
        for metric in metrics:
            platform = campaign_platform_map.get(metric.campaign_id)
            if platform:
                metrics_by_platform[platform].append(metric)
        
        # Calculate stats for each platform
        platform_stats = []
        for platform, platform_metrics in metrics_by_platform.items():
            if not platform_metrics:
                continue
            
            total_imp = sum(m.impressions or 0 for m in platform_metrics)
            total_clicks = sum(m.clicks or 0 for m in platform_metrics)
            total_cost = sum(m.cost or 0 for m in platform_metrics)
            total_conv = sum(m.conversions or 0 for m in platform_metrics)
            total_rev = sum(m.revenue or 0 for m in platform_metrics)
            
            ctr = (total_clicks / total_imp * 100) if total_imp > 0 else 0.0
            cpc = (total_cost / total_clicks) if total_clicks > 0 else 0.0
            roi = ((total_rev - total_cost) / total_cost * 100) if total_cost > 0 and total_rev > 0 else None
            
            platform_stats.append({
                "platform": platform,
                "impressions": int(total_imp),
                "clicks": int(total_clicks),
                "cost": round(total_cost, 2),
                "conversions": int(total_conv),
                "revenue": round(total_rev, 2) if total_rev > 0 else None,
                "ctr": round(ctr, 2),
                "cpc": round(cpc, 2),
                "roi": round(roi, 2) if roi else None,
                "campaigns_count": len(campaigns_by_platform[platform])
            })
        
        return platform_stats
    
    @staticmethod
    def _get_top_campaigns(
        db: Session,
        campaign_ids: List[int],
        start_date: date,
        end_date: date,
        limit: int = 5
    ) -> List[Dict[str, Any]]:
        """Get top performing campaigns by ROI"""
        # Get aggregated metrics per campaign
        campaign_stats = db.query(
            Metric.campaign_id,
            func.sum(Metric.cost).label('total_cost'),
            func.sum(Metric.conversions).label('total_conversions'),
            func.sum(Metric.revenue).label('total_revenue')
        ).filter(
            Metric.campaign_id.in_(campaign_ids),
            Metric.date >= start_date,
            Metric.date <= end_date
        ).group_by(
            Metric.campaign_id
        ).all()
        
        # Calculate ROI and sort
        campaigns_with_roi = []
        for stat in campaign_stats:
            if stat.total_cost and stat.total_cost > 0 and stat.total_revenue and stat.total_revenue > 0:
                roi = ((stat.total_revenue - stat.total_cost) / stat.total_cost * 100)
                campaigns_with_roi.append({
                    "campaign_id": stat.campaign_id,
                    "cost": float(stat.total_cost),
                    "revenue": float(stat.total_revenue),  # Store revenue
                    "conversions": int(stat.total_conversions or 0),
                    "roi": roi
                })
        
        # Sort by ROI descending
        campaigns_with_roi.sort(key=lambda x: x['roi'], reverse=True)
        
        # Get campaign details for top ones
        top_campaign_ids = [c['campaign_id'] for c in campaigns_with_roi[:limit]]
        campaigns = db.query(Campaign).filter(Campaign.id.in_(top_campaign_ids)).all()
        
        campaign_map = {c.id: c for c in campaigns}
        
        # Build response
        top_campaigns = []
        for stat in campaigns_with_roi[:limit]:
            campaign = campaign_map.get(stat['campaign_id'])
            if campaign:
                top_campaigns.append({
                    "id": campaign.id,
                    "name": campaign.name,
                    "platform": campaign.platform or "unknown",
                    "cost": round(stat['cost'], 2),
                    "conversions": stat['conversions'],
                    "revenue": round(stat.get('revenue', 0), 2),  # Add revenue!
                    "roi": round(stat['roi'], 2)
                })
        
        return top_campaigns
    
    @staticmethod
    def _empty_dashboard(start_date: date, end_date: date) -> Dict[str, Any]:
        """Return empty dashboard when no campaigns exist"""
        return {
            "start_date": start_date,
            "end_date": end_date,
            "total_impressions": 0,
            "total_clicks": 0,
            "total_cost": 0.0,
            "total_conversions": 0,
            "total_revenue": None,
            "overall_ctr": 0.0,
            "overall_cpc": 0.0,
            "overall_cpa": None,
            "overall_roi": None,
            "platforms": [],
            "top_campaigns": [],
            "active_insights_count": 0,
            "total_campaigns": 0,
            "connected_platforms": 0
        }