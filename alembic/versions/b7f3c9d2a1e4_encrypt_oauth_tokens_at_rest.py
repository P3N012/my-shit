"""encrypt oauth tokens at rest

Encrypts any existing plaintext access/refresh tokens on
platform_connections in place. The column type is unchanged (text);
only the stored values are rewritten as Fernet ciphertext.

Revision ID: b7f3c9d2a1e4
Revises: e0af0e51d9e6
Create Date: 2026-05-22 15:30:00.000000

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

from app.core.crypto import encrypt, is_encrypted

# revision identifiers, used by Alembic.
revision: str = 'b7f3c9d2a1e4'
down_revision: Union[str, None] = 'e0af0e51d9e6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    bind = op.get_bind()
    rows = bind.execute(
        sa.text(
            "SELECT id, access_token, refresh_token FROM platform_connections"
        )
    ).fetchall()

    for row in rows:
        updates = {}
        if row.access_token is not None and not is_encrypted(row.access_token):
            updates["access_token"] = encrypt(row.access_token)
        if row.refresh_token is not None and not is_encrypted(row.refresh_token):
            updates["refresh_token"] = encrypt(row.refresh_token)
        if not updates:
            continue
        set_clause = ", ".join(f"{col} = :{col}" for col in updates)
        bind.execute(
            sa.text(
                f"UPDATE platform_connections SET {set_clause} WHERE id = :id"
            ),
            {**updates, "id": row.id},
        )


def downgrade() -> None:
    # Decryption requires the app key, so we don't auto-revert to plaintext.
    # Downgrading the schema is a no-op; the ciphertext stays in place.
    pass
