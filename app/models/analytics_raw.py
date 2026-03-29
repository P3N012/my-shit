"""
AnalyticsRaw model - Granular analytics data with dimensions

This model handles:
- Detailed breakdowns (age, gender, location, device)
- Audience analysis data
- More granular than daily campaign metrics
"""

from sqlalchemy import Column, Integer, String, Float, Date, ForeignKey
from sqlalchemy.orm import relationship
from app.core.database import Base


class AnalyticsRaw(Base):
    """Granular analytics data with demographic breakdowns"""
    __tablename__ = "analytics_raw"

    # Primary fields
    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=False)
    date = Column(Date, nullable=False, index=True)
    
    # Dimensions (breakdowns)
    platform = Column(String, nullable=False)
    device = Column(String, nullable=False)  # 'Mobile', 'Desktop', 'Tablet'
    country = Column(String, nullable=False)  # ISO country code
    city = Column(String, nullable=True)
    age_range = Column(String, nullable=True)  # '18-24', '25-34', etc.
    gender = Column(String, nullable=True)  # 'Male', 'Female', 'Unknown'
    
    # Metrics
    impressions = Column(Integer, default=0)
    clicks = Column(Integer, default=0)
    cost = Column(Float, default=0.0)
    conversions = Column(Integer, default=0)
    revenue = Column(Float, default=0.0, nullable=True)
    
    # Relationship
    campaign = relationship("Campaign")

    def __repr__(self):
        return f"<AnalyticsRaw(campaign_id={self.campaign_id}, date={self.date}, device='{self.device}')>"