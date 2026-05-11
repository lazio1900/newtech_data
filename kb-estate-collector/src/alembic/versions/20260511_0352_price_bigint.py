"""price columns to bigint

kb_prices.{general_price, high_avg_price, low_avg_price}, transactions.price 를
INTEGER (32bit, 21.47억 한계) → BIGINT 로 변경. 세종/강남 등 21억 초과 단지 INSERT 실패 해결.
ORM 모델은 이미 BigInteger 라 코드 변경 없음.

Revision ID: 2bae7eaf6d73
Revises: e4f5a6b7c8d9
Create Date: 2026-05-11
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "2bae7eaf6d73"
down_revision: Union[str, None] = "e4f5a6b7c8d9"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.alter_column(
        "kb_prices",
        "general_price",
        existing_type=sa.Integer(),
        type_=sa.BigInteger(),
        existing_nullable=True,
    )
    op.alter_column(
        "kb_prices",
        "high_avg_price",
        existing_type=sa.Integer(),
        type_=sa.BigInteger(),
        existing_nullable=True,
    )
    op.alter_column(
        "kb_prices",
        "low_avg_price",
        existing_type=sa.Integer(),
        type_=sa.BigInteger(),
        existing_nullable=True,
    )
    op.alter_column(
        "transactions",
        "price",
        existing_type=sa.Integer(),
        type_=sa.BigInteger(),
        existing_nullable=False,
    )


def downgrade() -> None:
    # 21억 초과 값이 들어가 있으면 INTEGER 로 다운그레이드 시 손실. 신중히 사용.
    op.alter_column(
        "transactions",
        "price",
        existing_type=sa.BigInteger(),
        type_=sa.Integer(),
        existing_nullable=False,
    )
    op.alter_column(
        "kb_prices",
        "low_avg_price",
        existing_type=sa.BigInteger(),
        type_=sa.Integer(),
        existing_nullable=True,
    )
    op.alter_column(
        "kb_prices",
        "high_avg_price",
        existing_type=sa.BigInteger(),
        type_=sa.Integer(),
        existing_nullable=True,
    )
    op.alter_column(
        "kb_prices",
        "general_price",
        existing_type=sa.BigInteger(),
        type_=sa.Integer(),
        existing_nullable=True,
    )
