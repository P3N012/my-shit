"""
Campaign model - Marketing campaigns from connected platforms

This model handles:
- Campaign information synced from platforms
- Mapping between our IDs and platform IDs
- Campaign status tracking
"""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Date
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base


class Campaign(Base):
    """Marketing campaign (synced from Google Ads, Meta Ads, etc.)"""
    __tablename__ = "campaigns"

    # Primary fields
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    connection_id = Column(Integer, ForeignKey("platform_connections.id"), nullable=False)
    
    # Campaign identification
    platform_campaign_id = Column(String, nullable=False)  # ID from platform (Google/Meta)
    name = Column(String, nullable=False)
    
    # Campaign details
    platform = Column(String, nullable=False)  # 'google_ads', 'meta_ads'
    status = Column(String, nullable=True)  # 'active', 'paused', 'ended', 'archived'
    
    # Campaign dates
    start_date = Column(Date, nullable=True)
    end_date = Column(Date, nullable=True)
    
    # Budget info (optional for MVP)
    budget = Column(String, nullable=True)  # Store as string for now (currency handling later)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)  # When we first synced
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    last_synced_at = Column(DateTime, nullable=True)  # Last time we updated from platform
    
    # Unique constraint: platform_campaign_id must be unique per connection
    __table_args__ = (
        # UniqueConstraint('connection_id', 'platform_campaign_id', name='uq_connection_platform_campaign'),
    )
    
    # Relationships
    user = relationship("User", back_populates="campaigns")
    connection = relationship("PlatformConnection", back_populates="campaigns")
    metrics = relationship("Metric", back_populates="campaign", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<Campaign(id={self.id}, name='{self.name}', platform='{self.platform}')>"