from collections import defaultdict
from datetime import datetime
from typing import Iterable, List, Optional

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy import func
from sqlalchemy.orm import Session

from src.core.config import settings
from src.core.database import get_db
from src.core.time import now_kst
from src.models import Complex, CrawlRun, CrawlTask, RunStatus, TaskStatus

router = APIRouter()


# Pydantic schemas
class TaskSchema(BaseModel):
    id: int
    task_key: str
    status: TaskStatus
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    retry_count: int
    items_collected: int
    items_saved: int
    error_type: Optional[str]
    error_message: Optional[str]

    class Config:
        from_attributes = True


class RunSchema(BaseModel):
    id: int
    job_id: Optional[int]
    status: RunStatus
    started_at: Optional[datetime]
    finished_at: Optional[datetime]
    total_tasks: int
    success_count: int
    failed_count: int
    skipped_count: int
    prepare_total: int = 0
    prepare_done_count: int = 0
    created_at: datetime

    class Config:
        from_attributes = True


class TargetComplexSchema(BaseModel):
    id: int
    name: str
    address: str
    region_code: Optional[str]


class RunDetailSchema(RunSchema):
    tasks: List[TaskSchema] = []
    target_complexes: List[TargetComplexSchema] = []


def _extract_complex_ids(task_keys: Iterable[str]) -> List[int]:
    """task_key 들에서 complex_id 를 추출"""
    cids: set[int] = set()
    for task_key in task_keys:
        parts = task_key.split("_")
        try:
            if parts[0] == "kb" and len(parts) >= 3:
                cids.add(int(parts[2]))
        except (ValueError, IndexError):
            continue
    return sorted(cids)


def _apply_live_counts(schema_obj, run_id: int, counts: Optional[dict]) -> None:
    """RUNNING/PENDING run 의 실시간 진행 카운트를 스키마에 덮어쓴다.

    저장된 success/failed/skipped_count 는 finalize 전까지 0 이므로, 진행 중인 run 은
    crawl_tasks 집계로 실제 진행률을 보여준다.
    """
    if not counts:
        return
    schema_obj.success_count = counts.get(TaskStatus.SUCCESS, 0)
    schema_obj.failed_count = counts.get(TaskStatus.FAILED, 0)
    schema_obj.skipped_count = counts.get(TaskStatus.SKIPPED, 0)


class RunListItemSchema(RunSchema):
    target_summary: str = ""


@router.get("/", response_model=List[RunListItemSchema])
def list_runs(
    skip: int = 0,
    limit: int = 100,
    job_id: Optional[int] = None,
    status_filter: Optional[RunStatus] = None,
    db: Session = Depends(get_db),  # noqa: B008
):
    """실행 이력 목록 조회"""
    query = db.query(CrawlRun).order_by(CrawlRun.created_at.desc())

    if job_id:
        query = query.filter(CrawlRun.job_id == job_id)

    if status_filter:
        query = query.filter(CrawlRun.status == status_filter)

    runs = query.offset(skip).limit(limit).all()
    if not runs:
        return []

    # run 마다 tasks/complexes 를 개별 조회하면 N+1 → 전체를 2번의 IN 쿼리로 일괄 처리.
    run_ids = [r.id for r in runs]
    keys_by_run: dict[int, List[str]] = defaultdict(list)
    for run_id, task_key in (
        db.query(CrawlTask.run_id, CrawlTask.task_key).filter(CrawlTask.run_id.in_(run_ids)).all()
    ):
        keys_by_run[run_id].append(task_key)

    cids_by_run = {run.id: _extract_complex_ids(keys_by_run.get(run.id, [])) for run in runs}
    all_cids = {cid for cids in cids_by_run.values() for cid in cids}
    name_by_cid = (
        dict(db.query(Complex.id, Complex.name).filter(Complex.id.in_(all_cids)).all())
        if all_cids
        else {}
    )

    # RUNNING/PENDING run 은 저장 카운트가 finalize 전까지 0 이므로 실시간 집계로 덮어쓴다.
    active_ids = [r.id for r in runs if r.status in (RunStatus.RUNNING, RunStatus.PENDING)]
    live_counts: dict[int, dict] = {}
    if active_ids:
        for rid, st, cnt in (
            db.query(CrawlTask.run_id, CrawlTask.status, func.count())
            .filter(CrawlTask.run_id.in_(active_ids))
            .group_by(CrawlTask.run_id, CrawlTask.status)
            .all()
        ):
            live_counts.setdefault(rid, {})[st] = cnt

    results = []
    for run in runs:
        names = [name_by_cid[c] for c in cids_by_run[run.id] if c in name_by_cid]
        if not names:
            summary = ""
        elif len(names) <= 3:
            summary = ", ".join(names)
        else:
            summary = f"{names[0]} 외 {len(names) - 1}개 단지"

        item = RunListItemSchema.model_validate(run)
        item.target_summary = summary
        _apply_live_counts(item, run.id, live_counts.get(run.id))
        results.append(item)

    return results


@router.get("/{run_id}")
def get_run(run_id: int, db: Session = Depends(get_db)):  # noqa: B008
    """실행 상세 조회 (태스크 + 대상 단지 포함)"""
    run = db.query(CrawlRun).filter(CrawlRun.id == run_id).first()

    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")

    cids = _extract_complex_ids(t.task_key for t in run.tasks)
    target_complexes = []
    if cids:
        complexes = db.query(Complex).filter(Complex.id.in_(cids)).all()
        target_complexes = [
            TargetComplexSchema(
                id=c.id,
                name=c.name,
                address=c.address,
                region_code=c.region_code,
            )
            for c in complexes
        ]

    detail = RunDetailSchema.model_validate(run)
    detail.target_complexes = target_complexes

    if run.status in (RunStatus.RUNNING, RunStatus.PENDING):
        counts = dict(
            db.query(CrawlTask.status, func.count())
            .filter(CrawlTask.run_id == run_id)
            .group_by(CrawlTask.status)
            .all()
        )
        _apply_live_counts(detail, run_id, counts)

    return detail


@router.get("/{run_id}/tasks", response_model=List[TaskSchema])
def get_run_tasks(
    run_id: int,
    skip: int = 0,
    limit: int = 100,
    status_filter: Optional[TaskStatus] = None,
    db: Session = Depends(get_db),  # noqa: B008
):
    """실행의 태스크 목록 조회"""
    query = db.query(CrawlTask).filter(CrawlTask.run_id == run_id)

    if status_filter:
        query = query.filter(CrawlTask.status == status_filter)

    tasks = query.offset(skip).limit(limit).all()
    return tasks


def _purge_broker_queue() -> int:
    """취소 시 잔여 큐 메시지 제거 (worker self-skip churn 방지). 실패해도 무시.

    _run_cancelled 가드가 보조 안전망이라 purge 가 실패해도 정확성엔 영향 없다.
    """
    try:
        import redis

        client = redis.from_url(settings.celery_broker_url)
        try:
            depth = int(client.llen("celery"))
            client.delete("celery")
            return depth
        finally:
            client.close()
    except Exception:
        return 0


@router.post("/{run_id}/cancel")
def cancel_run(run_id: int, db: Session = Depends(get_db)):  # noqa: B008
    """진행 중인 run 을 즉시 취소(CANCELLED 로 terminal 마킹 + 큐 purge).

    finished==total 도달을 기다리지 않고 즉시 종료한다 — prefetch 잔여 task 는
    _run_cancelled 가드로 self-skip 된다.
    """
    run = db.query(CrawlRun).filter(CrawlRun.id == run_id).first()
    if not run:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Run not found")
    if run.status not in (RunStatus.RUNNING, RunStatus.PENDING):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"이미 종료된 run 입니다 ({run.status.value})",
        )

    counts = dict(
        db.query(CrawlTask.status, func.count())
        .filter(CrawlTask.run_id == run_id)
        .group_by(CrawlTask.status)
        .all()
    )
    run.success_count = counts.get(TaskStatus.SUCCESS, 0)
    run.failed_count = counts.get(TaskStatus.FAILED, 0)
    run.skipped_count = counts.get(TaskStatus.SKIPPED, 0)
    run.status = RunStatus.CANCELLED
    run.finished_at = now_kst()
    run.error_summary = '{"reason": "manual_cancel"}'
    db.commit()

    purged = _purge_broker_queue()
    return {"run_id": run_id, "status": "cancelled", "purged_messages": purged}
