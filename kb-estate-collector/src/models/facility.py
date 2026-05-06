"""단지별 주변 시설 정보.

학군/지하철/병원/CCTV/전기차충전소 등 다양한 시설을 단일 테이블로 정규화.
facility_type 으로 구분하고 sub_type 으로 세분 (e.g., 학교과정 / 지하철호선).
"""
from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    Float,
    ForeignKey,
    Index,
    Integer,
    String,
    UniqueConstraint,
)
from sqlalchemy.dialects.postgresql import JSONB
from sqlalchemy.orm import relationship

from src.core.database import Base


class ComplexFacility(Base):
    """단지 주변 시설."""

    __tablename__ = "complex_facilities"

    id = Column(Integer, primary_key=True, index=True)
    complex_id = Column(Integer, ForeignKey("complexes.id"), nullable=False)

    # 시설 분류
    facility_type = Column(String(20), nullable=False, comment="대분류: school/subway/hospital/cctv/ev_charger/park/mart/bank")
    sub_type = Column(String(40), nullable=True, comment="소분류: kindergarten/preschool/elementary/middle/high, line2 등")

    # 시설 정보
    external_id = Column(String(80), nullable=True, comment="KB 내부 식별자 (학교식별자 등)")
    name = Column(String(200), nullable=False, comment="시설명")
    address = Column(String(500), nullable=True, comment="주소")
    phone = Column(String(40), nullable=True)

    # 위치
    distance_m = Column(Integer, nullable=True, comment="단지로부터의 거리 (m)")
    lat = Column(Float, nullable=True)
    lng = Column(Float, nullable=True)

    # 원본 응답 (확장성 위해)
    meta = Column(JSONB, nullable=True, comment="원본 응답 (총학생수/노선번호/시설등급 등)")

    # 메타데이터
    fetched_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    created_at = Column(DateTime, nullable=False, default=datetime.utcnow)
    updated_at = Column(DateTime, nullable=False, default=datetime.utcnow, onupdate=datetime.utcnow)

    complex = relationship("Complex")

    __table_args__ = (
        UniqueConstraint("complex_id", "facility_type", "external_id", name="uq_facility_complex_type_extid"),
        Index("ix_facility_complex_type", "complex_id", "facility_type"),
    )
