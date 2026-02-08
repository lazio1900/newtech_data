from typing import List, Optional, Dict, Any
from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from sqlalchemy import func
from pydantic import BaseModel

from src.core.database import get_db
from src.models import Complex, Area, PriorityLevel
from src.models.crawl import CrawlRun, CrawlTask, RunStatus

router = APIRouter()


# Pydantic schemas
class AreaSchema(BaseModel):
    id: Optional[int] = None
    exclusive_m2: float
    supply_m2: Optional[float] = None
    pyeong: Optional[float] = None
    kb_area_code: Optional[str] = None

    class Config:
        from_attributes = True


class ComplexCreateSchema(BaseModel):
    name: str
    address: str
    region_code: Optional[str] = None
    kb_complex_id: Optional[str] = None
    priority: PriorityLevel = PriorityLevel.NORMAL
    is_active: bool = True
    collect_listings: bool = True


class ComplexSchema(BaseModel):
    id: int
    name: str
    address: str
    region_code: Optional[str]
    kb_complex_id: Optional[str]
    priority: PriorityLevel
    is_active: bool
    collect_listings: bool
    areas: List[AreaSchema] = []

    class Config:
        from_attributes = True


@router.get("/", response_model=List[ComplexSchema])
def list_complexes(
    skip: int = 0,
    limit: int = 100,
    is_active: Optional[bool] = None,
    db: Session = Depends(get_db),
):
    """단지 목록 조회"""
    query = db.query(Complex)
    
    if is_active is not None:
        query = query.filter(Complex.is_active == is_active)
    
    complexes = query.order_by(Complex.name).offset(skip).limit(limit).all()
    return complexes


@router.get("/{complex_id}", response_model=ComplexSchema)
def get_complex(complex_id: int, db: Session = Depends(get_db)):
    """단지 상세 조회"""
    complex = db.query(Complex).filter(Complex.id == complex_id).first()
    
    if not complex:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Complex not found"
        )
    
    return complex


@router.post("/", response_model=ComplexSchema, status_code=status.HTTP_201_CREATED)
def create_complex(
    complex_data: ComplexCreateSchema,
    db: Session = Depends(get_db),
):
    """단지 등록"""
    complex = Complex(**complex_data.model_dump())
    db.add(complex)
    db.commit()
    db.refresh(complex)
    
    return complex


@router.patch("/{complex_id}", response_model=ComplexSchema)
def update_complex(
    complex_id: int,
    complex_data: dict,
    db: Session = Depends(get_db),
):
    """단지 정보 수정"""
    complex = db.query(Complex).filter(Complex.id == complex_id).first()
    
    if not complex:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Complex not found"
        )
    
    for key, value in complex_data.items():
        if hasattr(complex, key):
            setattr(complex, key, value)
    
    db.commit()
    db.refresh(complex)
    
    return complex


@router.delete("/{complex_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_complex(complex_id: int, db: Session = Depends(get_db)):
    """단지 삭제"""
    complex = db.query(Complex).filter(Complex.id == complex_id).first()
    
    if not complex:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Complex not found"
        )
    
    db.delete(complex)
    db.commit()

    return None


@router.post("/{complex_id}/collect", status_code=status.HTTP_202_ACCEPTED)
def collect_complex(complex_id: int, db: Session = Depends(get_db)):
    """단지 즉시 수집 (시세 + 실거래 + 매물)"""
    complex_obj = db.query(Complex).filter(Complex.id == complex_id).first()
    if not complex_obj:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Complex not found",
        )

    from src.workers.tasks import run_kb_collection

    run = CrawlRun(
        job_id=None,
        status=RunStatus.PENDING,
        started_at=datetime.utcnow(),
    )
    db.add(run)
    db.commit()

    target_config = f'{{"complex_ids": [{complex_id}]}}'
    task = run_kb_collection.delay(
        job_id=None, run_id=run.id, target_config=target_config,
    )

    return {
        "message": f"{complex_obj.name} 수집이 시작되었습니다",
        "run_id": run.id,
        "task_id": task.id,
    }


class BatchCollectSchema(BaseModel):
    complex_ids: List[int]


@router.post("/batch-collect", status_code=status.HTTP_202_ACCEPTED)
def batch_collect_complexes(
    body: BatchCollectSchema,
    db: Session = Depends(get_db),
):
    """여러 단지 일괄 수집"""
    if not body.complex_ids:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="complex_ids is empty",
        )

    complexes = (
        db.query(Complex)
        .filter(Complex.id.in_(body.complex_ids))
        .all()
    )
    if not complexes:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="No complexes found",
        )

    from src.workers.tasks import run_kb_collection

    run = CrawlRun(
        job_id=None,
        status=RunStatus.PENDING,
        started_at=datetime.utcnow(),
    )
    db.add(run)
    db.commit()

    import json
    target_config = json.dumps({"complex_ids": body.complex_ids})
    task = run_kb_collection.delay(
        job_id=None, run_id=run.id, target_config=target_config,
    )

    return {
        "message": f"{len(complexes)}개 단지 수집이 시작되었습니다",
        "run_id": run.id,
        "task_id": task.id,
        "count": len(complexes),
    }


@router.get("/last-runs")
def get_complex_last_runs(db: Session = Depends(get_db)):
    """각 단지의 마지막 수집 상태를 반환"""
    # CrawlTask.task_key에서 complex_id를 추출하여 가장 최신 run 정보를 매핑
    # task_key format: kb_price_{complex_id}_{area_id}, kb_transaction_{complex_id}, kb_listing_{complex_id}
    from sqlalchemy import text

    # 모든 task를 가져와 complex_id별 가장 최신 run 정보를 추출
    tasks = (
        db.query(CrawlTask, CrawlRun)
        .join(CrawlRun, CrawlTask.run_id == CrawlRun.id)
        .order_by(CrawlRun.started_at.desc())
        .all()
    )

    result: Dict[int, Any] = {}
    for task, run in tasks:
        # task_key에서 complex_id 추출
        parts = task.task_key.split("_")
        try:
            # kb_price_3_1 → complex_id=3, kb_transaction_3 → complex_id=3
            if parts[0] == "kb" and len(parts) >= 3:
                cid = int(parts[2])
            else:
                continue
        except (ValueError, IndexError):
            continue

        if cid not in result:
            result[cid] = {
                "run_id": run.id,
                "status": run.status.value if hasattr(run.status, 'value') else str(run.status),
                "started_at": run.started_at.isoformat() if run.started_at else None,
                "finished_at": run.finished_at.isoformat() if run.finished_at else None,
            }

    return result


@router.post("/discover-region")
async def discover_region(
    region_code: str,
    db: Session = Depends(get_db),
):
    """
    지역코드로 아파트 단지 자동 발견 및 등록.

    동기 실행 후 결과를 바로 반환합니다.

    - region_code: 법정동코드 (5자리 시군구 또는 10자리 법정동)
    - 예: "11680" (강남구), "1168010100" (역삼동)
    """
    from src.services.complex_discovery import ComplexDiscoveryService

    service = ComplexDiscoveryService(db)
    result = await service.discover_complexes(region_code)

    return {
        "region_code": result["region_code"],
        "total_found": result["total_found"],
        "new_registered": result["new_registered"],
        "already_exists": result["already_exists"],
    }
