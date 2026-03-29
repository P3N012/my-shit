"""
PlatformConnection model - OAuth tokens and platform connection status

This model handles:
- OAuth access and refresh tokens (encrypted)
- Connection status tracking
- Platform account information
- Last sync timestamp
"""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base


class PlatformConnection(Base):
    """Platform OAuth connection (Google Ads, Meta Ads, etc.)"""
    __tablename__ = "platform_connections"

    # Primary fields
    id = Column(Integer, primary_key=True, index=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    
    # Platform info
    platform = Column(String, nullable=False)  # 'google_ads', 'meta_ads'
    account_id = Column(String, nullable=False)  # Platform's account ID
    account_name = Column(String, nullable=True)  # User-friendly account name
    
    # OAuth tokens (ENCRYPTED in production!)
    # For MVP: Store as-is, add encryption in V2
    access_token = Column(Text, nullable=False)
    refresh_token = Column(Text, nullable=True)  # Google has this, Meta doesn't
    token_expires_at = Column(DateTime, nullable=True)
    
    # Connection status
    # Options: 'disconnected', 'connecting', 'active', 'syncing', 'error'
    status = Column(String, default='active', nullable=False)
    error_message = Column(Text, nullable=True)  # Last error if status='error'
    
    # Sync tracking
    last_sync_at = Column(DateTime, nullable=True)
    sync_status = Column(String, default='never')  # 'never', 'success', 'failed', 'in_progress'
    consecutive_failures = Column(Integer, default=0)  # Track failures for error handling
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    # Unique constraint: user can connect same account only once
    __table_args__ = (
        # UniqueConstraint('user_id', 'platform', 'account_id', name='uq_user_platform_account'),
    )
    
    # Relationships
    user = relationship("User", back_populates="platform_connections")
    campaigns = relationship("Campaign", back_populates="connection", cascade="all, delete-orphan")
    sync_logs = relationship("SyncLog", back_populates="connection", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<PlatformConnection(id={self.id}, platform='{self.platform}', status='{self.status}')>"