"""
Metric model - Daily performance metrics for campaigns

This model handles:
- Daily aggregated metrics from platforms
- Performance data (impressions, clicks, cost, conversions, revenue)
- Deduplication (upsert on campaign_id + date)
"""

from sqlalchemy import Column, Integer, Float, String, DateTime, Date, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base


class Metric(Base):
    """Daily performance metrics for a campaign"""
    __tablename__ = "metrics"

    # Primary fields
    id = Column(Integer, primary_key=True, index=True)
    campaign_id = Column(Integer, ForeignKey("campaigns.id"), nullable=False)
    date = Column(Date, nullable=False, index=True)  # Date of metrics
    
    # Performance metrics (from platform)
    impressions = Column(Integer, default=0)
    clicks = Column(Integer, default=0)
    conversions = Column(Integer, default=0)
    cost = Column(Float, default=0.0)  # In account currency
    revenue = Column(Float, default=0.0, nullable=True)  # May not be tracked
    
    # Currency (for future multi-currency support)
    currency = Column(String, default='USD', nullable=False)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Unique constraint: one metric record per campaign per date
    __table_args__ = (
        # UniqueConstraint('campaign_id', 'date', name='uq_campaign_date'),
    )
    
    # Relationship
    campaign = relationship("Campaign", back_populates="metrics")

    def __repr__(self):
        return f"<Metric(campaign_id={self.campaign_id}, date={self.date}, cost={self.cost})>"
    
    # Calculated properties (computed on-the-fly)
    @property
    def ctr(self):
        """Click-through rate"""
        if self.impressions == 0:
            return 0.0
        return (self.clicks / self.impressions) * 100
    
    @property
    def cpc(self):
        """Cost per click"""
        if self.clicks == 0:
            return 0.0
        return self.cost / self.clicks
    
    @property
    def cpa(self):
        """Cost per acquisition"""
        if self.conversions == 0:
            return None  # Not 0, not infinity - truly undefined
        return self.cost / self.conversions
    
    @property
    def cvr(self):
        """Conversion rate"""
        if self.clicks == 0:
            return 0.0
        return (self.conversions / self.clicks) * 100
    
    @property
    def roi(self):
        """Return on investment (percentage)"""
        if self.cost == 0 or self.revenue is None:
            return None
        return ((self.revenue - self.cost) / self.cost) * 100
    
    @property
    def roas(self):
        """Return on ad spend (ratio)"""
        if self.cost == 0 or self.revenue is None:
            return None
        return self.revenue / self.cost