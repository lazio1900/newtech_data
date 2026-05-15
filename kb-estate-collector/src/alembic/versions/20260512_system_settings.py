"""system_settings 테이블 신설 — 전역 토글 (listings_enabled 등) 보관.

Revision ID: 9b2c5a8e7d31
Revises: 7c1a9e4f3b21
Create Date: 2026-05-12
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "9b2c5a8e7d31"
down_revision: Union[str, None] = "7c1a9e4f3b21"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "system_settings",
        sa.Column("key", sa.String(length=80), primary_key=True),
        sa.Column("value", sa.String(length=200), nullable=False),
        sa.Column("description", sa.String(length=300), nullable=True),
        sa.Column("updated_at", sa.DateTime(), nullable=True),
    )
    # listings_enabled 기본값 'true' (현재 동작 유지)
    op.execute(
        "INSERT INTO system_settings (key, value, description) "
        "VALUES ('listings_enabled', 'true', '매물(호가) 수집 활성화 여부') "
        "ON CONFLICT (key) DO NOTHING"
    )


def downgrade() -> None:
    op.drop_table("system_settings")
