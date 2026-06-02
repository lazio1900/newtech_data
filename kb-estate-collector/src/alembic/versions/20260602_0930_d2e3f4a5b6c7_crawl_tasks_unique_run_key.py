"""crawl_tasks UNIQUE(run_id, task_key) + 누락 인덱스 정리

acks_late + reject_on_worker_lost 환경에서 동일 task_key 가 redeliver 로 2개 이상
INSERT 되어 완료 카운트를 흔들던 문제를 차단. 그룹별 1개(SUCCESS·최신 우선)만 남기고
중복 제거 후 UNIQUE 인덱스를 건다.

부수: 모델이 선언했으나 실제 DB 에 없던 idx_task_run_status(run_id, status) 를 생성한다
(스키마 드리프트). finalize/drain-sweep 의 status GROUP BY 가 이 인덱스에 의존한다.
"""

from typing import Sequence, Union

from alembic import op

revision: str = "d2e3f4a5b6c7"
down_revision: Union[str, None] = "c1d2e3f4a5b6"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


# (run_id, task_key) 그룹마다 살릴 row: SUCCESS 우선 → 최신 활동 → 큰 id. rn>1 이 중복.
_RANKED = """
    SELECT id, row_number() OVER (
        PARTITION BY run_id, task_key
        ORDER BY (status = 'SUCCESS') DESC, COALESCE(finished_at, created_at) DESC, id DESC
    ) AS rn
    FROM crawl_tasks
"""


def upgrade() -> None:
    # 버려질 task 의 raw_payloads 먼저 제거(고아 방지) 후 중복 task 제거.
    # 윈도우 함수 + PK anti-join — NOT IN 의 O(n^2) 회피.
    op.execute(
        f"DELETE FROM raw_payloads p USING ({_RANKED}) d " f"WHERE p.task_id = d.id AND d.rn > 1"
    )
    op.execute(f"DELETE FROM crawl_tasks t USING ({_RANKED}) d WHERE t.id = d.id AND d.rn > 1")

    # 스키마 드리프트 정리 (모델 선언과 실제 DB 일치화).
    op.execute("DROP INDEX IF EXISTS idx_task_key")
    op.execute("CREATE INDEX IF NOT EXISTS idx_task_run_status ON crawl_tasks (run_id, status)")
    op.create_index("uq_task_run_key", "crawl_tasks", ["run_id", "task_key"], unique=True)


def downgrade() -> None:
    op.drop_index("uq_task_run_key", table_name="crawl_tasks")
