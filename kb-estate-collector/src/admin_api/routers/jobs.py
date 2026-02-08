from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime

from src.core.database import get_db
from src.models import CrawlJob, JobType, JobStatus
from src.workers.tasks import (
    run_kb_price_collection,
    run_transaction_collection,
    run_listing_collection,
    run_region_collection,
)

router = APIRouter()


# Pydantic schemas
class JobCreateSchema(BaseModel):
    name: str
    job_type: JobType
    description: Optional[str] = None
    target_config: Optional[str] = None
    cron_schedule: Optional[str] = None
    max_concurrency: int = 5
    rate_limit_per_minute: int = 60


class JobSchema(BaseModel):
    id: int
    name: str
    job_type: JobType
    description: Optional[str]
    status: JobStatus
    cron_schedule: Optional[str]
    max_concurrency: int
    rate_limit_per_minute: int
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


@router.get("/", response_model=List[JobSchema])
def list_jobs(
    skip: int = 0,
    limit: int = 100,
    status_filter: Optional[JobStatus] = None,
    db: Session = Depends(get_db),
):
    """수집 작업 목록 조회"""
    query = db.query(CrawlJob)
    
    if status_filter:
        query = query.filter(CrawlJob.status == status_filter)
    
    jobs = query.offset(skip).limit(limit).all()
    return jobs


@router.get("/{job_id}", response_model=JobSchema)
def get_job(job_id: int, db: Session = Depends(get_db)):
    """작업 상세 조회"""
    job = db.query(CrawlJob).filter(CrawlJob.id == job_id).first()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    return job


@router.post("/", response_model=JobSchema, status_code=status.HTTP_201_CREATED)
def create_job(
    job_data: JobCreateSchema,
    db: Session = Depends(get_db),
):
    """수집 작업 생성"""
    job = CrawlJob(**job_data.model_dump())
    db.add(job)
    db.commit()
    db.refresh(job)
    
    return job


@router.post("/{job_id}/run", status_code=status.HTTP_202_ACCEPTED)
def run_job_now(job_id: int, db: Session = Depends(get_db)):
    """작업 즉시 실행"""
    job = db.query(CrawlJob).filter(CrawlJob.id == job_id).first()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    if job.status != JobStatus.ACTIVE:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Job is not active"
        )
    
    # Trigger appropriate task based on job type
    task_map = {
        JobType.KB_PRICE: run_kb_price_collection,
        JobType.KB_LISTING: run_listing_collection,
        JobType.KB_TRANSACTION: run_transaction_collection,
        JobType.MOLIT_TRANSACTION: run_transaction_collection,
    }

    task_fn = task_map.get(job.job_type)
    if not task_fn:
        raise HTTPException(
            status_code=status.HTTP_501_NOT_IMPLEMENTED,
            detail=f"Job type {job.job_type} not yet implemented"
        )

    task = task_fn.delay(job_id=job.id)

    return {
        "message": "Job execution started",
        "job_id": job.id,
        "task_id": task.id,
    }


@router.patch("/{job_id}/pause")
def pause_job(job_id: int, db: Session = Depends(get_db)):
    """작업 일시 중지"""
    job = db.query(CrawlJob).filter(CrawlJob.id == job_id).first()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    job.status = JobStatus.PAUSED
    db.commit()
    
    return {"message": "Job paused", "job_id": job.id}


@router.patch("/{job_id}/resume")
def resume_job(job_id: int, db: Session = Depends(get_db)):
    """작업 재개"""
    job = db.query(CrawlJob).filter(CrawlJob.id == job_id).first()
    
    if not job:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Job not found"
        )
    
    job.status = JobStatus.ACTIVE
    db.commit()

    return {"message": "Job resumed", "job_id": job.id}


@router.post("/run-region", status_code=status.HTTP_202_ACCEPTED)
def run_region_collection_endpoint(
    region_code: str,
    job_id: Optional[int] = None,
    db: Session = Depends(get_db),
):
    """
    지역 기반 전체 수집 (발견 + 시세 + 실거래가 + 매물).

    - region_code: 법정동코드 (5자리 시군구 또는 10자리)
    - job_id: 연결할 CrawlJob ID (선택)
    """
    task = run_region_collection.delay(region_code=region_code, job_id=job_id)
    return {
        "message": f"Region collection started for {region_code}",
        "task_id": task.id,
    }
