"""add dong_code and dong_name to complexes

Revision ID: b1c2d3e4f5a6
Revises: a5db41cb5594
Create Date: 2026-05-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


revision: str = "b1c2d3e4f5a6"
down_revision: Union[str, None] = "a5db41cb5594"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "complexes",
        sa.Column("dong_code", sa.String(length=10), nullable=True, comment="법정동코드 (10자리)"),
    )
    op.add_column(
        "complexes",
        sa.Column("dong_name", sa.String(length=50), nullable=True, comment="법정동명"),
    )
    op.create_index("ix_complexes_dong_code", "complexes", ["dong_code"])


def downgrade() -> None:
    op.drop_index("ix_complexes_dong_code", table_name="complexes")
    op.drop_column("complexes", "dong_name")
    op.drop_column("complexes", "dong_code")
