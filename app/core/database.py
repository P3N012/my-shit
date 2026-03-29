"""
Database configuration and session management

Handles:
- SQLAlchemy engine creation
- Session management
- Base class for models
- Database initialization
"""

from sqlalchemy import create_engine
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import sessionmaker, Session
from typing import Generator

from app.core.config import settings

# Create SQLAlchemy engine
engine = create_engine(
    settings.DATABASE_URL,
    pool_pre_ping=True,  # Verify connections before using
    pool_size=10,        # Connection pool size
    max_overflow=20,     # Max overflow connections
    echo=settings.is_development  # Log SQL in development
)

# Session factory
SessionLocal = sessionmaker(
    autocommit=False,
    autoflush=False,
    bind=engine
)

# Base class for all models
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    """
    Dependency function for FastAPI routes.
    
    Provides a database session and ensures it's closed after use.
    
    Usage:
        @router.get("/users")
        def get_users(db: Session = Depends(get_db)):
            return db.query(User).all()
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """
    Initialize database - create all tables.
    
    This should be called once during application startup
    or via a separate initialization script.
    
    Note: In production, use Alembic migrations instead.
    """
    # Import all models so they're registered with Base
    from app.models import (
        User, RefreshToken, PlatformConnection,
        Campaign, Metric, SyncLog,
        AnalyticsRaw, Insight, ReportPreference
    )
    
    # Create all tables
    Base.metadata.create_all(bind=engine)
    print("✅ Database tables created successfully!")


def drop_all_tables() -> None:
    """
    Drop all tables. 
    
    ⚠️  USE WITH CAUTION! 
    Only use in development for clean slate.
    NEVER use in production!
    """
    if settings.is_production:
        raise RuntimeError("Cannot drop tables in production!")
    
    Base.metadata.drop_all(bind=engine)
    print("⚠️  All tables dropped!")