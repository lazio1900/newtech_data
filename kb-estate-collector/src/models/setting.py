"""전역 시스템 설정 — key/value 토글.

예) listings_enabled = 'true' | 'false' — 매물(호가) 수집 활성화 여부.
환경변수와 달리 worker 재시작 없이 즉시 반영.
"""
from sqlalchemy import Column, DateTime, String

from src.core.database import Base
from src.core.time import now_kst


class SystemSetting(Base):
    __tablename__ = "system_settings"

    key = Column(String(80), primary_key=True, comment="설정 키")
    value = Column(String(200), nullable=False, comment="설정 값 (문자열)")
    description = Column(String(300), nullable=True, comment="설명/메모")
    updated_at = Column(DateTime, default=now_kst, onupdate=now_kst)
