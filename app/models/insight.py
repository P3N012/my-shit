"""
Insight model - AI-generated insights and alerts

This model handles:
- Automated insight generation
- Insight types (trends, anomalies, recommendations)
- User dismissal tracking
"""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base


class Insight(Base):
    """AI-generated insight or alert for user"""
    __tablename__ = "insights"

    # Primary fields
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Insight type
    # Options: 'performance_trend', 'platform_comparison', 'underperforming_campaign',
    #          'budget_pacing', 'cpa_alert', 'spend_anomaly', 'conversion_drop'
    type = Column(String, nullable=False)
    
    # Severity
    # Options: 'positive', 'negative', 'caution', 'info'
    severity = Column(String, nullable=False)
    
    # Content
    message = Column(String, nullable=False)  # Short message
    detail = Column(Text, nullable=True)  # Longer explanation
    
    # Related entities (JSON for flexibility)
    related_campaigns = Column(JSON, nullable=True)  # [campaign_id1, campaign_id2]
    related_platforms = Column(JSON, nullable=True)  # ['google_ads', 'meta_ads']
    
    # Metadata
    data = Column(JSON, nullable=True)  # Additional data (percentages, values, etc.)
    
    # User interaction
    dismissed_at = Column(DateTime, nullable=True)
    action_taken = Column(String, nullable=True)  # What user did about it
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    expires_at = Column(DateTime, nullable=True)  # Auto-archive after X days
    
    # Relationship
    user = relationship("User", back_populates="insights")

    def __repr__(self):
        return f"<Insight(id={self.id}, type='{self.type}', severity='{self.severity}')>"