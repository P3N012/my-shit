"""
ReportPreference model - User email report settings

This model handles:
- Automated email report configuration
- Report frequency and content preferences
- Filter settings
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base


class ReportPreference(Base):
    """User preferences for automated email reports"""
    __tablename__ = "report_preferences"

    # Primary fields
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Enable/disable
    enabled = Column(Boolean, default=False)
    
    # Frequency
    # Options: 'weekly', 'monthly', 'custom'
    frequency = Column(String, default='weekly', nullable=False)
    
    # Scheduling
    day_of_week = Column(Integer, nullable=True)  # 0-6 (Monday-Sunday) for weekly
    day_of_month = Column(Integer, nullable=True)  # 1-31 for monthly
    custom_schedule = Column(JSON, nullable=True)  # For custom frequency
    time = Column(String, default='09:00', nullable=False)  # HH:MM format
    timezone = Column(String, default='UTC', nullable=False)
    
    # Content preferences
    include_overview = Column(Boolean, default=True)
    include_platform_breakdown = Column(Boolean, default=True)
    include_top_campaigns = Column(Boolean, default=True)
    include_bottom_campaigns = Column(Boolean, default=False)
    include_insights = Column(Boolean, default=True)
    include_audience_breakdown = Column(Boolean, default=False)
    
    # Filters
    filter_platforms = Column(JSON, nullable=True)  # ['google_ads'] or null for all
    filter_campaigns = Column(JSON, nullable=True)  # [123, 456] or null for all
    date_range_days = Column(Integer, default=7)  # 7, 30, or 90
    
    # Email settings
    email_addresses = Column(JSON, nullable=True)  # Additional CC recipients
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_sent_at = Column(DateTime, nullable=True)
    
    # Relationship
    user = relationship("User", back_populates="report_preferences")

    def __repr__(self):
        return f"<ReportPreference(user_id={self.user_id}, frequency='{self.frequency}', enabled={self.enabled})>"