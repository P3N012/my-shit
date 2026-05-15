"""Organization + Membership business logic."""

from typing import List, Optional

from sqlalchemy.orm import Session

from app.models.organization import (
    ROLE_MEMBER,
    ROLE_OWNER,
    Membership,
    Organization,
)


class OrganizationService:
    @staticmethod
    def create_organization(
        db: Session,
        name: str,
        owner_user_id: int,
    ) -> Organization:
        """Create an organization and make the caller its owner."""
        org = Organization(name=name)
        db.add(org)
        db.flush()  # need org.id for the membership

        db.add(
            Membership(
                user_id=owner_user_id,
                organization_id=org.id,
                role=ROLE_OWNER,
            )
        )
        db.commit()
        db.refresh(org)
        return org

    @staticmethod
    def list_user_organizations(
        db: Session,
        user_id: int,
    ) -> List[Organization]:
        return (
            db.query(Organization)
            .join(Membership, Membership.organization_id == Organization.id)
            .filter(Membership.user_id == user_id)
            .order_by(Organization.id.asc())
            .all()
        )

    @staticmethod
    def get_membership(
        db: Session,
        user_id: int,
        organization_id: int,
    ) -> Optional[Membership]:
        return (
            db.query(Membership)
            .filter(
                Membership.user_id == user_id,
                Membership.organization_id == organization_id,
            )
            .first()
        )

    @staticmethod
    def list_memberships(
        db: Session,
        user_id: int,
    ) -> List[Membership]:
        return (
            db.query(Membership).filter(Membership.user_id == user_id).all()
        )
