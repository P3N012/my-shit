"""
Campaign Schemas

Pydantic models for campaign endpoints.
"""

from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime, date


# ============================================================================
# Campaign Response
# ============================================================================

class CampaignResponse(BaseModel):
    """Response schema for single campaign"""
    id: int
    platform: str
    platform_campaign_id: str
    name: str
    status: Optional[str]
    start_date: Optional[date]
    end_date: Optional[date]
    created_at: datetime
    last_synced_at: Optional[datetime]
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "id": 1,
                "platform": "google_ads",
                "platform_campaign_id": "12345678",
                "name": "Summer Sale 2026",
                "status": "active",
                "start_date": "2026-02-01",
                "end_date": None,
                "created_at": "2026-02-27T10:00:00",
                "last_synced_at": "2026-02-28T09:00:00"
            }
        }


class CampaignListResponse(BaseModel):
    """Response schema for campaign list"""
    campaigns: List[CampaignResponse]
    total: int
    
    class Config:
        json_schema_extra = {
            "example": {
                "campaigns": [
                    {
                        "id": 1,
                        "platform": "google_ads",
                        "name": "Summer Sale 2026",
                        "status": "active"
                    }
                ],
                "total": 1
            }
        }


# ============================================================================
# Campaign Metrics
# ============================================================================

class MetricResponse(BaseModel):
    """Response schema for single metric"""
    date: date
    impressions: int
    clicks: int
    cost: float
    conversions: int
    revenue: Optional[float]
    ctr: float = Field(..., description="Click-through rate (%)")
    cpc: float = Field(..., description="Cost per click")
    cpa: Optional[float] = Field(None, description="Cost per acquisition")
    cvr: float = Field(..., description="Conversion rate (%)")
    roi: Optional[float] = Field(None, description="Return on investment (%)")
    
    class Config:
        from_attributes = True
        json_schema_extra = {
            "example": {
                "date": "2026-02-27",
                "impressions": 10000,
                "clicks": 500,
                "cost": 250.00,
                "conversions": 25,
                "revenue": 1250.00,
                "ctr": 5.0,
                "cpc": 0.50,
                "cpa": 10.00,
                "cvr": 5.0,
                "roi": 400.0
            }
        }


class CampaignMetricsResponse(BaseModel):
    """Response schema for campaign metrics"""
    campaign_id: int
    campaign_name: str
    metrics: List[MetricResponse]
    total_records: int
    
    # Summary stats
    summary: dict = Field(..., description="Aggregated metrics")
    
    class Config:
        json_schema_extra = {
            "example": {
                "campaign_id": 1,
                "campaign_name": "Summer Sale 2026",
                "metrics": [
                    {
                        "date": "2026-02-27",
                        "impressions": 10000,
                        "clicks": 500,
                        "cost": 250.00,
                        "conversions": 25,
                        "revenue": 1250.00,
                        "ctr": 5.0,
                        "cpc": 0.50,
                        "cpa": 10.00,
                        "cvr": 5.0,
                        "roi": 400.0
                    }
                ],
                "total_records": 30,
                "summary": {
                    "total_impressions": 300000,
                    "total_clicks": 15000,
                    "total_cost": 7500.00,
                    "total_conversions": 750,
                    "avg_ctr": 5.0,
                    "avg_cpc": 0.50
                }
            }
        }