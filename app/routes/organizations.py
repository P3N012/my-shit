"""Organization endpoints.

  GET  /orgs        List orgs the current user belongs to
  POST /orgs        Create a new org (caller becomes owner)
  GET  /orgs/{id}   Get a single org the user belongs to
"""

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.models.user import User
from app.schemas.auth import ErrorResponse
from app.schemas.organization import (
    OrganizationCreate,
    OrganizationListResponse,
    OrganizationResponse,
)
from app.services.organization_service import OrganizationService
from app.utils.dependencies import get_current_user

router = APIRouter(prefix="/orgs", tags=["Organizations"])


@router.get("", response_model=OrganizationListResponse)
def list_organizations(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    orgs = OrganizationService.list_user_organizations(db, current_user.id)
    return OrganizationListResponse(
        organizations=[OrganizationResponse.model_validate(o) for o in orgs],
        total=len(orgs),
    )


@router.post(
    "",
    response_model=OrganizationResponse,
    status_code=status.HTTP_201_CREATED,
)
def create_organization(
    request: OrganizationCreate,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    org = OrganizationService.create_organization(
        db, name=request.name, owner_user_id=current_user.id
    )
    return OrganizationResponse.model_validate(org)


@router.get(
    "/{org_id}",
    response_model=OrganizationResponse,
    responses={403: {"model": ErrorResponse}},
)
def get_organization(
    org_id: int,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    membership = OrganizationService.get_membership(
        db, user_id=current_user.id, organization_id=org_id
    )
    if membership is None:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="No access to this organization",
        )
    return OrganizationResponse.model_validate(membership.organization)
