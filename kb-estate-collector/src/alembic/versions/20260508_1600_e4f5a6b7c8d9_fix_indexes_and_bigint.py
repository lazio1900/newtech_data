"""fix listings.ask_price BigInteger + add missing unique/regular indexes

Revision ID: e4f5a6b7c8d9
Revises: d3e4f5a6b7c8
Create Date: 2026-05-08 16:00
"""
from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


revision: str = "e4f5a6b7c8d9"
down_revision: Union[str, Sequence[str], None] = "d3e4f5a6b7c8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # 1) listings.ask_price: integer → bigint (21억+ 매물 overflow 방지)
    op.alter_column(
        "listings", "ask_price",
        type_=sa.BigInteger(),
        existing_nullable=False,
    )

    # 2) 중복 transactions 정리 — UNIQUE 적용 전에 중복 row 제거
    #    같은 (complex_id, contract_date, price, exclusive_m2, floor) 가 여러 번이면
    #    가장 최근 fetched_at 만 남기고 나머지 삭제
    op.execute("""
    DELETE FROM transactions a
    USING transactions b
    WHERE a.complex_id   = b.complex_id
      AND a.contract_date = b.contract_date
      AND a.price        = b.price
      AND a.exclusive_m2 = b.exclusive_m2
      AND COALESCE(a.floor, -1) = COALESCE(b.floor, -1)
      AND a.id < b.id
    """)

    # 3) 누락 인덱스 추가 (모델에 정의된 것 DB 에 적용)
    # transactions
    op.create_index(
        "idx_transaction_complex_date", "transactions",
        ["complex_id", "contract_date"],
    )
    op.create_index(
        "idx_transaction_unique", "transactions",
        ["complex_id", "contract_date", "price", "exclusive_m2", "floor"],
        unique=True,
    )

    # kb_prices
    op.create_index(
        "idx_kb_price_unique", "kb_prices",
        ["complex_id", "area_id", "as_of_date"],
        unique=True,
    )
    op.create_index(
        "idx_kb_price_fetched", "kb_prices",
        ["fetched_at"],
    )

    # listings
    op.create_index(
        "ix_listings_source_listing_id", "listings",
        ["source_listing_id"], unique=True,
    )
    op.create_index(
        "idx_listing_complex_status", "listings",
        ["complex_id", "status"],
    )
    op.create_index(
        "idx_listing_fetched", "listings",
        ["fetched_at"],
    )


def downgrade() -> None:
    op.drop_index("idx_listing_fetched", table_name="listings")
    op.drop_index("idx_listing_complex_status", table_name="listings")
    op.drop_index("ix_listings_source_listing_id", table_name="listings")
    op.drop_index("idx_kb_price_fetched", table_name="kb_prices")
    op.drop_index("idx_kb_price_unique", table_name="kb_prices")
    op.drop_index("idx_transaction_unique", table_name="transactions")
    op.drop_index("idx_transaction_complex_date", table_name="transactions")
    op.alter_column(
        "listings", "ask_price",
        type_=sa.Integer(),
        existing_nullable=False,
    )
