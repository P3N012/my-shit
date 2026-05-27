"""add connection auth_method

Adds platform_connections.auth_method to distinguish OAuth (Stripe
Connect) connections from read-only restricted-API-key connections.
Existing rows default to 'oauth'.

Revision ID: c4e8a1f5b6d2
Revises: b7f3c9d2a1e4
Create Date: 2026-05-22 16:10:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = 'c4e8a1f5b6d2'
down_revision: Union[str, None] = 'b7f3c9d2a1e4'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        'platform_connections',
        sa.Column(
            'auth_method',
            sa.String(),
            nullable=False,
            server_default='oauth',
        ),
    )


def downgrade() -> None:
    op.drop_column('platform_connections', 'auth_method')
