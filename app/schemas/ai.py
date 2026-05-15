"""Pydantic schemas for /api/v1/ai/*."""

from datetime import datetime
from typing import Any, Dict, List, Literal, Optional

from pydantic import BaseModel, ConfigDict, Field


class ChatMessage(BaseModel):
    role: Literal["user", "assistant"]
    content: str


class MessagesRequest(BaseModel):
    messages: List[ChatMessage] = Field(..., min_length=1)
    system: Optional[str] = Field(default=None, max_length=200_000)
    model: Optional[str] = Field(default=None, description="Override the default model")
    max_tokens: Optional[int] = Field(default=None, ge=1, le=128_000)


class TokenUsageSchema(BaseModel):
    input_tokens: int = 0
    output_tokens: int = 0
    cache_creation_input_tokens: int = 0
    cache_read_input_tokens: int = 0


class MessagesResponse(BaseModel):
    text: str
    model: str
    stop_reason: Optional[str]
    usage: TokenUsageSchema
    cost_usd: str  # serialized Decimal


class JobCreatedResponse(BaseModel):
    job_id: int
    status: str


class JobStatusResponse(BaseModel):
    id: int
    kind: str
    status: str
    result: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    created_at: datetime
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class UsageSummaryResponse(BaseModel):
    calls: int
    input_tokens: int
    output_tokens: int
    cache_read_input_tokens: int
    cost_usd: str
