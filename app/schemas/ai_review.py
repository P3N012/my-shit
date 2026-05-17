"""Schemas for /api/v1/ai/reviews/*."""

from datetime import datetime
from typing import Any, Dict, Optional

from pydantic import BaseModel, ConfigDict


class AIReviewResponse(BaseModel):
    id: int
    period_start: datetime
    period_end: datetime
    model: str
    content: str
    metrics_snapshot: Optional[Dict[str, Any]] = None
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)
