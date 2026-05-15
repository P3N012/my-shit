"""Schemas for Organization and Membership endpoints."""

from datetime import datetime
from typing import List

from pydantic import BaseModel, ConfigDict, Field


class OrganizationCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=200)


class OrganizationResponse(BaseModel):
    id: int
    name: str
    created_at: datetime

    model_config = ConfigDict(from_attributes=True)


class MembershipResponse(BaseModel):
    organization_id: int
    organization_name: str
    role: str

    model_config = ConfigDict(from_attributes=True)


class OrganizationListResponse(BaseModel):
    organizations: List[OrganizationResponse]
    total: int
