"""complex_facilities.name VARCHAR(200) → VARCHAR(500)

KB 가 한 위치에 다수 시설을 파이프(|) 구분으로 합쳐서 200자 초과 응답하는 경우가
있어 StringDataRightTruncation → InFailedSqlTransaction 으로 master task 까지 죽이는
케이스 차단.

Revision ID: 7c1a9e4f3b21
Revises: 2bae7eaf6d73
Create Date: 2026-05-12
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "7c1a9e4f3b21"
down_revision: Union[str, None] = "2bae7eaf6d73"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "complex_facilities",
        "name",
        existing_type=sa.String(length=200),
        type_=sa.String(length=500),
        existing_nullable=False,
    )


def downgrade() -> None:
    # 200자 초과 행이 있으면 truncate 후 다운그레이드해야 안전.
    op.alter_column(
        "complex_facilities",
        "name",
        existing_type=sa.String(length=500),
        type_=sa.String(length=200),
        existing_nullable=False,
    )
