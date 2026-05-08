"""
배치 설정 API — 시/도별 정기 크롤링 관리.

각 시/도는 하나의 CrawlJob(job_type=REGION_ALL)에 매핑되며,
해당 시/도에 등록된 모든 단지를 대상으로 수집합니다.
"""
from typing import Any, Dict, List, Optional
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel
import json

from src.core.database import get_db
from src.core.time import now_kst
from src.models import Complex, CrawlJob, CrawlRun, JobType, JobStatus, RunStatus

import logging
_logger = logging.getLogger(__name__)


def _sync_redbeat_entry(job_id: int, cron: Optional[str]) -> None:
    """DB 의 cron_schedule 을 redbeat entry 와 동기화.

    cron 이 None/빈문자열이면 entry 삭제. 아니면 등록/갱신.
    """
    try:
        from celery.schedules import crontab as celery_crontab
        from redbeat import RedBeatSchedulerEntry
        from src.workers.celery_app import celery_app
    except Exception as e:
        _logger.warning(f"redbeat import failed: {e}")
        return

    name = f"crawl-job-{job_id}"
    if not cron or not cron.strip():
        # 삭제
        try:
            entry = RedBeatSchedulerEntry.from_key(
                f"redbeat:{name}", app=celery_app,
            )
            entry.delete()
            _logger.info(f"[redbeat] removed entry for job {job_id}")
        except Exception:
            pass
        return

    parts = cron.strip().split()
    if len(parts) != 5:
        _logger.warning(f"[redbeat] invalid cron for job {job_id}: '{cron}'")
        return
    minute, hour, day, month, dow = parts
    try:
        schedule = celery_crontab(
            minute=minute, hour=hour, day_of_month=day,
            month_of_year=month, day_of_week=dow,
        )
        entry = RedBeatSchedulerEntry(
            name=name,
            task="src.workers.tasks.run_scheduled_job",
            schedule=schedule,
            args=[job_id],
            app=celery_app,
        )
        entry.save()
        _logger.info(f"[redbeat] synced entry for job {job_id}: {cron}")
    except Exception as e:
        _logger.warning(f"[redbeat] sync failed for job {job_id}: {e}")


router = APIRouter()

# 시/도 코드 → 이름 매핑 (프론트엔드 SIDO_REGIONS 동일)
SIDO_MAP: Dict[str, str] = {
    "11": "서울", "26": "부산", "27": "대구", "28": "인천",
    "29": "광주", "30": "대전", "31": "울산", "36": "세종",
    "41": "경기", "43": "충북", "44": "충남", "45": "전북",
    "46": "전남", "47": "경북", "48": "경남", "50": "제주",
}


def _find_batch_job(db: Session, sido_code: str) -> Optional[CrawlJob]:
    """시/도에 해당하는 배치 CrawlJob 조회"""
    target_json = json.dumps({"sido_code": sido_code})
    return db.query(CrawlJob).filter(
        CrawlJob.job_type == JobType.REGION_ALL,
        CrawlJob.target_config == target_json,
    ).first()


def _find_batch_job_by_target(db: Session, target: Dict) -> Optional[CrawlJob]:
    """임의 target_config 매칭 (sido_code/region_code/dong_code)."""
    target_json = json.dumps(target)
    return db.query(CrawlJob).filter(
        CrawlJob.job_type == JobType.REGION_ALL,
        CrawlJob.target_config == target_json,
    ).first()


def _build_last_runs(db: Session, job: Optional[CrawlJob]) -> List["BatchRunSchema"]:
    if not job:
        return []
    runs = (
        db.query(CrawlRun)
        .filter(CrawlRun.job_id == job.id)
        .order_by(CrawlRun.created_at.desc())
        .limit(5).all()
    )
    return [
        BatchRunSchema(
            id=r.id,
            status=r.status.value if hasattr(r.status, "value") else str(r.status),
            started_at=r.started_at.isoformat() if r.started_at else None,
            finished_at=r.finished_at.isoformat() if r.finished_at else None,
            total_tasks=r.total_tasks,
            success_count=r.success_count,
            failed_count=r.failed_count,
            skipped_count=r.skipped_count,
        )
        for r in runs
    ]


class BatchRunSchema(BaseModel):
    id: int
    status: str
    started_at: Optional[str]
    finished_at: Optional[str]
    total_tasks: int
    success_count: int
    failed_count: int
    skipped_count: int


class BatchSchema(BaseModel):
    sido_code: str
    sido_name: str
    complex_count: int
    job_id: Optional[int]
    job_status: Optional[str]
    cron_schedule: Optional[str]
    last_runs: List[BatchRunSchema]


class SigunguBatchSchema(BaseModel):
    region_code: str
    sigungu_name: str
    complex_count: int
    job_id: Optional[int]
    job_status: Optional[str]
    cron_schedule: Optional[str]
    last_runs: List[BatchRunSchema]


class DongBatchSchema(BaseModel):
    dong_code: str
    dong_name: str
    complex_count: int
    job_id: Optional[int]
    job_status: Optional[str]
    cron_schedule: Optional[str]
    last_runs: List[BatchRunSchema]


@router.get("/", response_model=List[BatchSchema])
def list_batches(db: Session = Depends(get_db)):
    """시/도별 배치 목록 (단지 수, 스케줄, 최근 실행 포함)"""
    # 시/도별 단지 수 집계
    rows = (
        db.query(
            func.substr(Complex.region_code, 1, 2).label("sido"),
            func.count(Complex.id).label("cnt"),
        )
        .filter(Complex.region_code.isnot(None), Complex.is_active.is_(True))
        .group_by("sido")
        .all()
    )
    count_map = {r.sido: r.cnt for r in rows}

    # 배치용 CrawlJob 전체 조회
    jobs = (
        db.query(CrawlJob)
        .filter(CrawlJob.job_type == JobType.REGION_ALL)
        .all()
    )
    job_map: Dict[str, CrawlJob] = {}
    for j in jobs:
        try:
            cfg = json.loads(j.target_config) if j.target_config else {}
            if "sido_code" in cfg:
                job_map[cfg["sido_code"]] = j
        except (json.JSONDecodeError, TypeError):
            pass

    result: List[BatchSchema] = []
    for sido_code, sido_name in SIDO_MAP.items():
        job = job_map.get(sido_code)
        last_runs: List[BatchRunSchema] = []

        if job:
            runs = (
                db.query(CrawlRun)
                .filter(CrawlRun.job_id == job.id)
                .order_by(CrawlRun.created_at.desc())
                .limit(5)
                .all()
            )
            for r in runs:
                last_runs.append(BatchRunSchema(
                    id=r.id,
                    status=r.status.value if hasattr(r.status, "value") else str(r.status),
                    started_at=r.started_at.isoformat() if r.started_at else None,
                    finished_at=r.finished_at.isoformat() if r.finished_at else None,
                    total_tasks=r.total_tasks,
                    success_count=r.success_count,
                    failed_count=r.failed_count,
                    skipped_count=r.skipped_count,
                ))

        result.append(BatchSchema(
            sido_code=sido_code,
            sido_name=sido_name,
            complex_count=count_map.get(sido_code, 0),
            job_id=job.id if job else None,
            job_status=job.status.value if job else None,
            cron_schedule=job.cron_schedule if job else None,
            last_runs=last_runs,
        ))

    return result


@router.post("/{sido_code}/run", status_code=status.HTTP_202_ACCEPTED)
def run_batch(sido_code: str, db: Session = Depends(get_db)):
    """시/도 배치 즉시 실행 — 해당 시/도의 모든 활성 단지 수집"""
    if sido_code not in SIDO_MAP:
        raise HTTPException(status_code=400, detail=f"Invalid sido_code: {sido_code}")

    complexes = (
        db.query(Complex)
        .filter(
            Complex.region_code.like(f"{sido_code}%"),
            Complex.is_active.is_(True),
        )
        .all()
    )
    if not complexes:
        raise HTTPException(
            status_code=404,
            detail=f"{SIDO_MAP[sido_code]}에 등록된 단지가 없습니다",
        )

    # 배치 Job이 없으면 생성
    job = _find_batch_job(db, sido_code)
    if not job:
        job = CrawlJob(
            name=f"{SIDO_MAP[sido_code]} 배치 수집",
            job_type=JobType.REGION_ALL,
            target_config=json.dumps({"sido_code": sido_code}),
            status=JobStatus.ACTIVE,
        )
        db.add(job)
        db.commit()

    # CrawlRun 생성
    run = CrawlRun(
        job_id=job.id,
        status=RunStatus.PENDING,
        started_at=now_kst(),
    )
    db.add(run)
    db.commit()

    from src.workers.tasks import run_kb_collection

    complex_ids = [c.id for c in complexes]
    target_config = json.dumps({"complex_ids": complex_ids})
    task = run_kb_collection.delay(
        job_id=job.id, run_id=run.id, target_config=target_config,
    )

    return {
        "message": f"{SIDO_MAP[sido_code]} {len(complexes)}개 단지 수집 시작",
        "run_id": run.id,
        "task_id": task.id,
        "complex_count": len(complexes),
    }


class ScheduleUpdateSchema(BaseModel):
    cron_schedule: Optional[str] = None


@router.patch("/{sido_code}/schedule")
def update_batch_schedule(
    sido_code: str,
    body: ScheduleUpdateSchema,
    db: Session = Depends(get_db),
):
    """시/도 배치 스케줄 설정/수정"""
    if sido_code not in SIDO_MAP:
        raise HTTPException(status_code=400, detail=f"Invalid sido_code: {sido_code}")

    job = _find_batch_job(db, sido_code)
    if not job:
        job = CrawlJob(
            name=f"{SIDO_MAP[sido_code]} 배치 수집",
            job_type=JobType.REGION_ALL,
            target_config=json.dumps({"sido_code": sido_code}),
            status=JobStatus.ACTIVE,
        )
        db.add(job)

    job.cron_schedule = body.cron_schedule
    db.commit()

    # redbeat sync (즉시 반영)
    _sync_redbeat_entry(job.id, body.cron_schedule)

    return {
        "message": "스케줄이 저장되었습니다",
        "sido_code": sido_code,
        "cron_schedule": job.cron_schedule,
    }


# ──────────────────────────────────────────────────────
# 시군구 / 동 단위 배치 (드릴다운)
# ──────────────────────────────────────────────────────

@router.get("/sigungu", response_model=List[SigunguBatchSchema])
def list_sigungu_batches(sido_code: str, db: Session = Depends(get_db)):
    """시도 산하 시군구별 배치 목록 (단지 수, 잡 상태)."""
    if sido_code not in SIDO_MAP:
        raise HTTPException(status_code=400, detail=f"Invalid sido_code: {sido_code}")

    rows = (
        db.query(
            Complex.region_code,
            func.count(Complex.id).label("cnt"),
        )
        .filter(
            Complex.region_code.like(f"{sido_code}%"),
            Complex.region_code.isnot(None),
            Complex.is_active.is_(True),
        )
        .group_by(Complex.region_code)
        .order_by(func.count(Complex.id).desc())
        .all()
    )
    if not rows:
        return []

    # 시군구 명 조회 — Complex.address 첫 조각에서 추출 (시군구 매핑 부재)
    name_map: Dict[str, str] = {}
    sample_addr = (
        db.query(Complex.region_code, Complex.address)
        .filter(Complex.region_code.in_([r.region_code for r in rows]))
        .distinct(Complex.region_code)
        .all()
    )
    for rc, addr in sample_addr:
        if not addr:
            continue
        parts = addr.split()
        if len(parts) >= 2:
            name_map[rc] = parts[1]

    # 잡 일괄 조회
    region_codes = [r.region_code for r in rows]
    jobs = (
        db.query(CrawlJob)
        .filter(CrawlJob.job_type == JobType.REGION_ALL)
        .all()
    )
    job_by_region: Dict[str, CrawlJob] = {}
    for j in jobs:
        try:
            cfg = json.loads(j.target_config) if j.target_config else {}
            if cfg.get("region_code") in region_codes:
                job_by_region[cfg["region_code"]] = j
        except (json.JSONDecodeError, TypeError):
            pass

    result: List[SigunguBatchSchema] = []
    for r in rows:
        job = job_by_region.get(r.region_code)
        result.append(SigunguBatchSchema(
            region_code=r.region_code,
            sigungu_name=name_map.get(r.region_code, r.region_code),
            complex_count=r.cnt,
            job_id=job.id if job else None,
            job_status=(job.status.value if hasattr(job.status, "value") else str(job.status)) if job else None,
            cron_schedule=job.cron_schedule if job else None,
            last_runs=_build_last_runs(db, job),
        ))
    return result


@router.get("/dong", response_model=List[DongBatchSchema])
def list_dong_batches(region_code: str, db: Session = Depends(get_db)):
    """시군구 산하 동별 배치 목록."""
    rows = (
        db.query(
            Complex.dong_code,
            Complex.dong_name,
            func.count(Complex.id).label("cnt"),
        )
        .filter(
            Complex.region_code == region_code,
            Complex.dong_code.isnot(None),
            Complex.is_active.is_(True),
        )
        .group_by(Complex.dong_code, Complex.dong_name)
        .order_by(func.count(Complex.id).desc())
        .all()
    )
    if not rows:
        return []

    dong_codes = [r.dong_code for r in rows]
    jobs = db.query(CrawlJob).filter(CrawlJob.job_type == JobType.REGION_ALL).all()
    job_by_dong: Dict[str, CrawlJob] = {}
    for j in jobs:
        try:
            cfg = json.loads(j.target_config) if j.target_config else {}
            if cfg.get("dong_code") in dong_codes:
                job_by_dong[cfg["dong_code"]] = j
        except (json.JSONDecodeError, TypeError):
            pass

    result: List[DongBatchSchema] = []
    for r in rows:
        job = job_by_dong.get(r.dong_code)
        result.append(DongBatchSchema(
            dong_code=r.dong_code,
            dong_name=r.dong_name or r.dong_code,
            complex_count=r.cnt,
            job_id=job.id if job else None,
            job_status=(job.status.value if hasattr(job.status, "value") else str(job.status)) if job else None,
            cron_schedule=job.cron_schedule if job else None,
            last_runs=_build_last_runs(db, job),
        ))
    return result


# 시군구/동 단위 run/schedule (일반화)

class ScopedRunSchema(BaseModel):
    scope: str   # 'sigungu' | 'dong'
    code: str    # region_code or dong_code


@router.post("/scoped/run", status_code=status.HTTP_202_ACCEPTED)
def run_scoped_batch(body: ScopedRunSchema, db: Session = Depends(get_db)):
    """시군구 또는 동 단위 배치 즉시 실행."""
    if body.scope == "sigungu":
        target = {"region_code": body.code}
        complexes = db.query(Complex).filter(
            Complex.region_code == body.code, Complex.is_active.is_(True),
        ).all()
        name = body.code
    elif body.scope == "dong":
        target = {"dong_code": body.code}
        complexes = db.query(Complex).filter(
            Complex.dong_code == body.code, Complex.is_active.is_(True),
        ).all()
        name = body.code
    else:
        raise HTTPException(status_code=400, detail="Invalid scope")

    if not complexes:
        raise HTTPException(status_code=404, detail=f"등록된 단지가 없습니다 ({body.scope}={body.code})")

    job = _find_batch_job_by_target(db, target)
    if not job:
        job = CrawlJob(
            name=f"{name} 배치 수집",
            job_type=JobType.REGION_ALL,
            target_config=json.dumps(target),
            status=JobStatus.ACTIVE,
        )
        db.add(job)
        db.commit()

    run = CrawlRun(job_id=job.id, status=RunStatus.PENDING, started_at=now_kst())
    db.add(run)
    db.commit()

    from src.workers.tasks import run_kb_collection
    target_config = json.dumps({"complex_ids": [c.id for c in complexes]})
    task = run_kb_collection.delay(job_id=job.id, run_id=run.id, target_config=target_config)

    return {
        "message": f"{name} {len(complexes)}개 단지 수집 시작",
        "run_id": run.id, "task_id": task.id, "complex_count": len(complexes),
    }


class ScopedScheduleSchema(BaseModel):
    scope: str
    code: str
    cron_schedule: Optional[str] = None


@router.patch("/scoped/schedule")
def update_scoped_schedule(body: ScopedScheduleSchema, db: Session = Depends(get_db)):
    """시군구/동 단위 배치 스케줄 설정/수정."""
    if body.scope == "sigungu":
        target = {"region_code": body.code}
    elif body.scope == "dong":
        target = {"dong_code": body.code}
    else:
        raise HTTPException(status_code=400, detail="Invalid scope")

    job = _find_batch_job_by_target(db, target)
    if not job:
        job = CrawlJob(
            name=f"{body.code} 배치 수집",
            job_type=JobType.REGION_ALL,
            target_config=json.dumps(target),
            status=JobStatus.ACTIVE,
        )
        db.add(job)
    job.cron_schedule = body.cron_schedule
    db.commit()
    _sync_redbeat_entry(job.id, body.cron_schedule)
    return {
        "message": "스케줄이 저장되었습니다",
        "scope": body.scope, "code": body.code,
        "cron_schedule": job.cron_schedule,
    }
