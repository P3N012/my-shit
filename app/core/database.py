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
    """Create all tables. Intended for dev use; introduce migrations before production."""
    import app.models  # noqa: F401 — register models with Base
    Base.metadata.create_all(bind=engine)


def drop_all_tables() -> None:
    """Drop all tables. Refuses to run in production."""
    if settings.is_production:
        raise RuntimeError("Cannot drop tables in production")
    Base.metadata.drop_all(bind=engine)