"""listings snapshot unique (source_listing_id, fetched_at)

Revision ID: a7b3e1f4d9c8
Revises: fca8e3ccc86f
Create Date: 2026-05-15 02:30:00.000000

매물을 snapshot 누적 구조로. source_listing_id 단일 UNIQUE 제거 →
(source_listing_id, fetched_at) UNIQUE. 같은 매물이라도 수집 시점별 row 가 누적.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "a7b3e1f4d9c8"
down_revision: Union[str, None] = "fca8e3ccc86f"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.drop_index("ix_listings_source_listing_id", table_name="listings")
    op.create_index("ix_listings_source_listing_id", "listings", ["source_listing_id"])
    op.create_index(
        "idx_listing_source_fetched",
        "listings",
        ["source_listing_id", "fetched_at"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("idx_listing_source_fetched", table_name="listings")
    op.drop_index("ix_listings_source_listing_id", table_name="listings")
    op.create_index("ix_listings_source_listing_id", "listings", ["source_listing_id"], unique=True)
