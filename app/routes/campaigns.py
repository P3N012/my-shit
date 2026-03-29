"""
Campaign Routes

API endpoints for campaigns:
- GET /campaigns - List all campaigns
- GET /campaigns/{id} - Get campaign details
- GET /campaigns/{id}/metrics - Get campaign metrics
"""

from fastapi import APIRouter, Depends, HTTPException, status, Query
from sqlalchemy.orm import Session
from typing import Optional
from datetime import date

from app.core.database import get_db
from app.schemas.campaign import (
    CampaignResponse,
    CampaignListResponse,
    MetricResponse,
    CampaignMetricsResponse
)
from app.services.campaign_service import CampaignService
from app.utils.dependencies import get_current_user
from app.models.user import User

router = APIRouter(prefix="/campaigns", tags=["Campaigns"])


@router.get(
    "",
    response_model=CampaignListResponse,
    summary="List all campaigns"
)
def list_campaigns(
    platform: Optional[str] = Query(None, description="Filter by platform (google_ads, meta_ads)"),
    status: Optional[str] = Query(None, description="Filter by status (active, paused, etc)"),
    limit: int = Query(100, ge=1, le=1000, description="Max results"),
    offset: int = Query(0, ge=0, description="Pagination offset"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get all campaigns for current user.
    
    **Filters:**
    - platform: google_ads, meta_ads
    - status: active, paused, ended, archived
    
    **Pagination:**
    - limit: Max results per page (default 100)
    - offset: Skip first N results
    
    **Returns:**
    - List of campaigns
    - Total count
    """
    campaigns, total = CampaignService.get_user_campaigns(
        db=db,
        user_id=current_user.id,
        platform=platform,
        status=status,
        limit=limit,
        offset=offset
    )
    
    return CampaignListResponse(
        campaigns=[CampaignResponse.model_validate(c) for c in campaigns],
        total=total
    )


@router.get(
    "/{campaign_id}",
    response_model=CampaignResponse,
    summary="Get campaign details"
)
def get_campaign(
    campaign_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get details of a specific campaign.
    
    **Returns:**
    - Campaign information
    
    **Errors:**
    - 404 if campaign not found or not owned by user
    """
    campaign = CampaignService.get_campaign(db, campaign_id, current_user.id)
    
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found"
        )
    
    return CampaignResponse.model_validate(campaign)


@router.get(
    "/{campaign_id}/metrics",
    response_model=CampaignMetricsResponse,
    summary="Get campaign metrics"
)
def get_campaign_metrics(
    campaign_id: int,
    start_date: Optional[date] = Query(None, description="Start date (default: 30 days ago)"),
    end_date: Optional[date] = Query(None, description="End date (default: today)"),
    limit: int = Query(90, ge=1, le=365, description="Max daily records"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get performance metrics for a campaign.
    
    **Date Range:**
    - Default: Last 30 days
    - Max: 365 days
    
    **Returns:**
    - Daily metrics (impressions, clicks, cost, conversions, etc.)
    - Aggregated summary stats
    - Calculated KPIs (CTR, CPC, CPA, ROI)
    
    **Errors:**
    - 404 if campaign not found
    """
    campaign = CampaignService.get_campaign(db, campaign_id, current_user.id)
    
    if not campaign:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Campaign not found"
        )
    
    metrics, summary = CampaignService.get_campaign_metrics(
        db=db,
        campaign_id=campaign_id,
        user_id=current_user.id,
        start_date=start_date,
        end_date=end_date,
        limit=limit
    )
    
    # Convert metrics to response format with calculated fields
    metric_responses = []
    for m in metrics:
        metric_responses.append(MetricResponse(
            date=m.date,
            impressions=m.impressions,
            clicks=m.clicks,
            cost=m.cost,
            conversions=m.conversions,
            revenue=m.revenue,
            ctr=m.ctr,
            cpc=m.cpc,
            cpa=m.cpa,
            cvr=m.cvr,
            roi=m.roi
        ))
    
    return CampaignMetricsResponse(
        campaign_id=campaign.id,
        campaign_name=campaign.name,
        metrics=metric_responses,
        total_records=len(metrics),
        summary=summary
    )