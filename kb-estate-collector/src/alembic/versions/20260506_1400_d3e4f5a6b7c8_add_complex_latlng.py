"""add lat/lng to complexes

Revision ID: d3e4f5a6b7c8
Revises: c2d3e4f5a6b7
Create Date: 2026-05-06
"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "d3e4f5a6b7c8"
down_revision: Union[str, None] = "c2d3e4f5a6b7"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("complexes", sa.Column("lat", sa.Float, nullable=True, comment="WGS84 위도"))
    op.add_column("complexes", sa.Column("lng", sa.Float, nullable=True, comment="WGS84 경도"))


def downgrade() -> None:
    op.drop_column("complexes", "lng")
    op.drop_column("complexes", "lat")
