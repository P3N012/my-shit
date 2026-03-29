"""
Models package - All database models

Import all models here so they're registered with SQLAlchemy Base.
This ensures all tables are created when Base.metadata.create_all() is called.
"""

from app.models.user import User, RefreshToken
from app.models.platform_connection import PlatformConnection
from app.models.campaign import Campaign
from app.models.metric import Metric
from app.models.sync_log import SyncLog
from app.models.analytics_raw import AnalyticsRaw
from app.models.insight import Insight
from app.models.report_preference import ReportPreference

__all__ = [
    "User",
    "RefreshToken",
    "PlatformConnection",
    "Campaign",
    "Metric",
    "SyncLog",
    "AnalyticsRaw",
    "Insight",
    "ReportPreference",
]