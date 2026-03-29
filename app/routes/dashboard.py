"""
Dashboard Routes

API endpoints for dashboard:
- GET /dashboard/overview - Complete dashboard overview
"""

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
from typing import Optional
from datetime import date

from app.core.database import get_db
from app.schemas.dashboard import DashboardOverviewResponse
from app.services.dashboard_service import DashboardService
from app.utils.dependencies import get_current_user
from app.models.user import User

router = APIRouter(prefix="/dashboard", tags=["Dashboard"])


@router.get(
    "/overview",
    response_model=DashboardOverviewResponse,
    summary="Get dashboard overview"
)
def get_dashboard_overview(
    start_date: Optional[date] = Query(None, description="Start date (default: 30 days ago)"),
    end_date: Optional[date] = Query(None, description="End date (default: today)"),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get complete dashboard overview with all stats.
    
    **Returns:**
    - Overall totals (impressions, clicks, cost, conversions, revenue)
    - Overall KPIs (CTR, CPC, CPA, ROI)
    - Platform breakdown (Google Ads vs Meta Ads)
    - Top 5 campaigns by ROI
    - Active insights count
    - Connected platforms count
    
    **Date Range:**
    - Default: Last 30 days
    - Max: 365 days
    
    **Use Case:**
    This single endpoint powers your entire dashboard view!
    """
    overview_data = DashboardService.get_overview(
        db=db,
        user_id=current_user.id,
        start_date=start_date,
        end_date=end_date
    )
    
    return DashboardOverviewResponse(**overview_data)