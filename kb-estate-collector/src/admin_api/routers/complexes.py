from typing import List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel

from src.core.database import get_db
from src.models import Complex, Area, PriorityLevel

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
    
    complexes = query.offset(skip).limit(limit).all()
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
