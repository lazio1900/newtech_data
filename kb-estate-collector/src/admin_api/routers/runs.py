from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from datetime import datetime

from src.core.database import get_db
from src.models import CrawlRun, CrawlTask, RunStatus, TaskStatus

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
    created_at: datetime

    class Config:
        from_attributes = True


class RunDetailSchema(RunSchema):
    tasks: List[TaskSchema] = []


@router.get("/", response_model=List[RunSchema])
def list_runs(
    skip: int = 0,
    limit: int = 100,
    job_id: Optional[int] = None,
    status_filter: Optional[RunStatus] = None,
    db: Session = Depends(get_db),
):
    """실행 이력 목록 조회"""
    query = db.query(CrawlRun).order_by(CrawlRun.created_at.desc())
    
    if job_id:
        query = query.filter(CrawlRun.job_id == job_id)
    
    if status_filter:
        query = query.filter(CrawlRun.status == status_filter)
    
    runs = query.offset(skip).limit(limit).all()
    return runs


@router.get("/{run_id}", response_model=RunDetailSchema)
def get_run(run_id: int, db: Session = Depends(get_db)):
    """실행 상세 조회 (태스크 포함)"""
    run = db.query(CrawlRun).filter(CrawlRun.id == run_id).first()
    
    if not run:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Run not found"
        )
    
    return run


@router.get("/{run_id}/tasks", response_model=List[TaskSchema])
def get_run_tasks(
    run_id: int,
    skip: int = 0,
    limit: int = 100,
    status_filter: Optional[TaskStatus] = None,
    db: Session = Depends(get_db),
):
    """실행의 태스크 목록 조회"""
    query = db.query(CrawlTask).filter(CrawlTask.run_id == run_id)
    
    if status_filter:
        query = query.filter(CrawlTask.status == status_filter)
    
    tasks = query.offset(skip).limit(limit).all()
    return tasks
