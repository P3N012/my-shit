"""
Models package - All database models

Import all models here so they're registered with SQLAlchemy Base.
This ensures all tables are created when Base.metadata.create_all() is called.
"""

from app.models.user import User, RefreshToken

__all__ = [
    "User",
    "RefreshToken",
]
