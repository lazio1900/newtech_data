"""add_trade_type_to_listings

Revision ID: fca8e3ccc86f
Revises: 9b2c5a8e7d31
Create Date: 2026-05-14 07:52:58.185954+00:00

"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "fca8e3ccc86f"
down_revision: Union[str, None] = "9b2c5a8e7d31"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("listings", sa.Column("trade_type", sa.String(10), nullable=True))


def downgrade() -> None:
    op.drop_column("listings", "trade_type")
