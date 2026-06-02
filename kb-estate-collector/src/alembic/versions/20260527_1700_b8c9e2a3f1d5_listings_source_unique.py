"""listings revert to source_listing_id unique (single row per source)

Revision ID: b8c9e2a3f1d5
Revises: a7b3e1f4d9c8
Create Date: 2026-05-27 17:00:00.000000

snapshot 누적 폐기 → 단지의 현재 호가만 유지하는 upsert + REMOVED 전이 모델로 회귀.
시계열은 KB 매물 ID 변동이 잦아 실제로는 누적되지 않았고(avg 1.14 row/source),
data_explorer 의 latest subquery 가 admin-api hang 의 원인 중 하나였음.
CLAUDE.md anti-pattern §5 의 권장 패턴 (seen_ids + REMOVED 전이) 로 원복.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "b8c9e2a3f1d5"
down_revision: Union[str, None] = "a7b3e1f4d9c8"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # source_listing_id 별 가장 최근 fetched_at(동률이면 id 큰 것) 만 살리고 나머지 삭제.
    # UNIQUE(source_listing_id) 로 복원하기 위한 dedupe.
    op.execute(
        """
        DELETE FROM listings a
        USING listings b
        WHERE a.source_listing_id = b.source_listing_id
          AND (a.fetched_at < b.fetched_at
               OR (a.fetched_at = b.fetched_at AND a.id < b.id))
        """
    )

    op.drop_index("idx_listing_source_fetched", table_name="listings")
    op.drop_index("ix_listings_source_listing_id", table_name="listings")
    op.create_index(
        "ix_listings_source_listing_id",
        "listings",
        ["source_listing_id"],
        unique=True,
    )


def downgrade() -> None:
    op.drop_index("ix_listings_source_listing_id", table_name="listings")
    op.create_index(
        "ix_listings_source_listing_id",
        "listings",
        ["source_listing_id"],
        unique=False,
    )
    op.create_index(
        "idx_listing_source_fetched",
        "listings",
        ["source_listing_id", "fetched_at"],
        unique=True,
    )
