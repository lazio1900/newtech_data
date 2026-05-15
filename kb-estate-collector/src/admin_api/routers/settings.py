"""전역 시스템 설정 (key/value) 조회·수정."""
from typing import Optional

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from src.core.database import get_db
from src.core.time import now_kst
from src.models import SystemSetting

router = APIRouter()


class SettingSchema(BaseModel):
    key: str
    value: str
    description: Optional[str] = None


class SettingUpdate(BaseModel):
    value: str


@router.get("/", response_model=list[SettingSchema])
def list_settings(db: Session = Depends(get_db)):
    rows = db.query(SystemSetting).order_by(SystemSetting.key).all()
    return [SettingSchema(key=r.key, value=r.value, description=r.description) for r in rows]


@router.get("/{key}", response_model=SettingSchema)
def get_setting(key: str, db: Session = Depends(get_db)):
    r = db.get(SystemSetting, key)
    if not r:
        raise HTTPException(status_code=404, detail=f"setting '{key}' not found")
    return SettingSchema(key=r.key, value=r.value, description=r.description)


@router.patch("/{key}", response_model=SettingSchema)
def update_setting(key: str, body: SettingUpdate, db: Session = Depends(get_db)):
    r = db.get(SystemSetting, key)
    if not r:
        raise HTTPException(status_code=404, detail=f"setting '{key}' not found")
    r.value = body.value
    r.updated_at = now_kst()
    db.commit()
    db.refresh(r)
    return SettingSchema(key=r.key, value=r.value, description=r.description)
