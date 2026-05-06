"""add complex_facilities table

Revision ID: c2d3e4f5a6b7
Revises: b1c2d3e4f5a6
Create Date: 2026-05-06

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import postgresql


revision: str = "c2d3e4f5a6b7"
down_revision: Union[str, None] = "b1c2d3e4f5a6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "complex_facilities",
        sa.Column("id", sa.Integer, primary_key=True),
        sa.Column("complex_id", sa.Integer, sa.ForeignKey("complexes.id"), nullable=False),
        sa.Column("facility_type", sa.String(20), nullable=False),
        sa.Column("sub_type", sa.String(40), nullable=True),
        sa.Column("external_id", sa.String(80), nullable=True),
        sa.Column("name", sa.String(200), nullable=False),
        sa.Column("address", sa.String(500), nullable=True),
        sa.Column("phone", sa.String(40), nullable=True),
        sa.Column("distance_m", sa.Integer, nullable=True),
        sa.Column("lat", sa.Float, nullable=True),
        sa.Column("lng", sa.Float, nullable=True),
        sa.Column("meta", postgresql.JSONB, nullable=True),
        sa.Column("fetched_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("created_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.Column("updated_at", sa.DateTime, nullable=False, server_default=sa.func.now()),
        sa.UniqueConstraint("complex_id", "facility_type", "external_id", name="uq_facility_complex_type_extid"),
    )
    op.create_index("ix_facility_complex_type", "complex_facilities", ["complex_id", "facility_type"])
    op.create_index("ix_complex_facilities_complex_id", "complex_facilities", ["complex_id"])


def downgrade() -> None:
    op.drop_index("ix_complex_facilities_complex_id", table_name="complex_facilities")
    op.drop_index("ix_facility_complex_type", table_name="complex_facilities")
    op.drop_table("complex_facilities")
