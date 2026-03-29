"""
Dashboard Schemas

Pydantic models for dashboard endpoints.
"""

from pydantic import BaseModel, Field
from typing import List, Optional
from datetime import date


# ============================================================================
# Dashboard Overview
# ============================================================================

class PlatformStats(BaseModel):
    """Stats for a single platform"""
    platform: str
    impressions: int
    clicks: int
    cost: float
    conversions: int
    revenue: Optional[float]
    ctr: float
    cpc: float
    roi: Optional[float]
    campaigns_count: int


class TopCampaign(BaseModel):
    """Top performing campaign summary"""
    id: int
    name: str
    platform: str
    cost: float
    conversions: int
    roi: Optional[float]


class DashboardOverviewResponse(BaseModel):
    """Complete dashboard overview"""
    
    # Date range
    start_date: date
    end_date: date
    
    # Overall totals
    total_impressions: int
    total_clicks: int
    total_cost: float
    total_conversions: int
    total_revenue: Optional[float]
    
    # Overall KPIs
    overall_ctr: float = Field(..., description="Overall click-through rate (%)")
    overall_cpc: float = Field(..., description="Overall cost per click")
    overall_cpa: Optional[float] = Field(None, description="Overall cost per acquisition")
    overall_roi: Optional[float] = Field(None, description="Overall ROI (%)")
    
    # Platform breakdown
    platforms: List[PlatformStats]
    
    # Top campaigns
    top_campaigns: List[TopCampaign] = Field(..., description="Top 5 campaigns by ROI")
    
    # Insights count
    active_insights_count: int
    
    # Metadata
    total_campaigns: int
    connected_platforms: int
    
    class Config:
        json_schema_extra = {
            "example": {
                "start_date": "2026-02-01",
                "end_date": "2026-03-02",
                "total_impressions": 500000,
                "total_clicks": 25000,
                "total_cost": 12500.00,
                "total_conversions": 1250,
                "total_revenue": 62500.00,
                "overall_ctr": 5.0,
                "overall_cpc": 0.50,
                "overall_cpa": 10.00,
                "overall_roi": 400.0,
                "platforms": [
                    {
                        "platform": "google_ads",
                        "impressions": 300000,
                        "clicks": 15000,
                        "cost": 7500.00,
                        "conversions": 750,
                        "revenue": 37500.00,
                        "ctr": 5.0,
                        "cpc": 0.50,
                        "roi": 400.0,
                        "campaigns_count": 3
                    }
                ],
                "top_campaigns": [
                    {
                        "id": 1,
                        "name": "Summer Sale 2026",
                        "platform": "google_ads",
                        "cost": 2500.00,
                        "conversions": 250,
                        "roi": 500.0
                    }
                ],
                "active_insights_count": 3,
                "total_campaigns": 5,
                "connected_platforms": 2
            }
        }