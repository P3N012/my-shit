"""
SyncLog model - Track all sync operations for debugging and monitoring

This model handles:
- Logging every sync attempt
- Success/failure tracking
- Error details for debugging
- Sync statistics
"""

from sqlalchemy import Column, Integer, String, DateTime, ForeignKey, Text, JSON
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base


class SyncLog(Base):
    """Log of sync operations for a platform connection"""
    __tablename__ = "sync_logs"

    # Primary fields
    id = Column(Integer, primary_key=True, index=True)
    connection_id = Column(Integer, ForeignKey("platform_connections.id"), nullable=False)
    
    # Sync timing
    started_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    completed_at = Column(DateTime, nullable=True)
    
    # Sync status
    # Options: 'in_progress', 'success', 'partial_success', 'failed', 'timeout'
    status = Column(String, default='in_progress', nullable=False)
    
    # Sync statistics
    campaigns_fetched = Column(Integer, default=0)
    campaigns_created = Column(Integer, default=0)
    campaigns_updated = Column(Integer, default=0)
    metrics_created = Column(Integer, default=0)
    metrics_updated = Column(Integer, default=0)
    
    # Error tracking
    error_message = Column(Text, nullable=True)
    error_code = Column(String, nullable=True)
    error_details = Column(JSON, nullable=True)  # Full error traceback if needed
    
    # Metadata
    triggered_by = Column(String, default='automatic')  # 'automatic', 'manual', 'retry'
    
    # Relationship
    connection = relationship("PlatformConnection", back_populates="sync_logs")

    def __repr__(self):
        return f"<SyncLog(id={self.id}, connection_id={self.connection_id}, status='{self.status}')>"
    
    @property
    def duration_seconds(self):
        """Calculate sync duration in seconds"""
        if self.completed_at is None:
            return None
        delta = self.completed_at - self.started_at
        return delta.total_seconds()