"""
User model - Authentication and account management

This model handles:
- User registration and authentication
- Account status (active, suspended, deleted)
- JWT refresh token management
- Relationships to all user-owned resources
"""

from sqlalchemy import Column, Integer, String, Boolean, DateTime, ForeignKey
from sqlalchemy.orm import relationship
from datetime import datetime
from app.core.database import Base


class User(Base):
    """User account model"""
    __tablename__ = "users"

    # Primary fields
    id = Column(Integer, primary_key=True, index=True)
    email = Column(String, unique=True, index=True, nullable=False)
    username = Column(String, unique=True, index=True, nullable=False)
    password = Column(String, nullable=False)  # Hashed with bcrypt
    
    # Account type
    is_admin = Column(Boolean, default=False)
    is_client = Column(Boolean, default=True)
    
    # Account status
    # Options: 'active', 'suspended', 'deleted'
    status = Column(String, default='active', nullable=False)
    
    # Subscription info (for billing - V2)
    subscription_tier = Column(String, default='starter')  # 'starter', 'professional'
    subscription_status = Column(String, default='trial')  # 'trial', 'active', 'cancelled'
    trial_ends_at = Column(DateTime, nullable=True)
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    deleted_at = Column(DateTime, nullable=True)  # Soft delete timestamp
    
    # Relationships
    refresh_tokens = relationship("RefreshToken", back_populates="user", cascade="all, delete-orphan")

    def __repr__(self):
        return f"<User(id={self.id}, email='{self.email}', status='{self.status}')>"


class RefreshToken(Base):
    """JWT refresh tokens for persistent authentication"""
    __tablename__ = "refresh_tokens"

    id = Column(Integer, primary_key=True, index=True)
    token = Column(String, unique=True, index=True, nullable=False)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False)
    expires_at = Column(DateTime, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationship
    user = relationship("User", back_populates="refresh_tokens")

    def __repr__(self):
        return f"<RefreshToken(user_id={self.user_id}, expires={self.expires_at})>"