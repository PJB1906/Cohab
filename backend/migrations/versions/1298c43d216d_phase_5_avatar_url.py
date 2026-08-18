"""phase 5 avatar url

Revision ID: 1298c43d216d
Revises: 1221949ea658
Create Date: 2026-08-18 12:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa

# revision identifiers, used by Alembic.
revision: str = '1298c43d216d'
down_revision: Union[str, None] = '1221949ea658'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('user', sa.Column('avatar_url', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('user', 'avatar_url')
