"""phase 6 phone number

Revision ID: 1eac5ce1061c
Revises: 1298c43d216d
Create Date: 2026-08-19 12:45:03.829411

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '1eac5ce1061c'
down_revision: Union[str, None] = '1298c43d216d'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('user', sa.Column('phone_number', sa.String(), nullable=True))


def downgrade() -> None:
    op.drop_column('user', 'phone_number')
