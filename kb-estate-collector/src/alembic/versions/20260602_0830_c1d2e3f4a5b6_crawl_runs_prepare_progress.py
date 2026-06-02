"""crawl_runs prepare 진행 추적 컬럼 (대용량 run 강건 완주)

prepare_total/prepare_done_count 로 prepare 단계 완료 게이트를 둬서, child 가 아직
enqueue 중인 시점에 run 이 조기 마감되지 않게 한다. drain-sweep 마감 판정의 보조 신호.
완료 감지가 leaf push 트리거 단독에 의존하지 않도록 하는 P0 변경의 일부.
"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

revision: str = "c1d2e3f4a5b6"
down_revision: Union[str, None] = "b8c9e2a3f1d5"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column(
        "crawl_runs",
        sa.Column("prepare_total", sa.Integer(), nullable=False, server_default="0"),
    )
    op.add_column(
        "crawl_runs",
        sa.Column("prepare_done_count", sa.Integer(), nullable=False, server_default="0"),
    )


def downgrade() -> None:
    op.drop_column("crawl_runs", "prepare_done_count")
    op.drop_column("crawl_runs", "prepare_total")
