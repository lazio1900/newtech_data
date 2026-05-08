from datetime import datetime
from src.core.time import now_kst
from sqlalchemy import Column, Integer, String, DateTime, Float, Boolean, ForeignKey, Text, Enum
from sqlalchemy.orm import relationship
import enum
from src.core.database import Base


class PriorityLevel(str, enum.Enum):
    """단지 수집 우선순위"""
    HIGH = "high"
    NORMAL = "normal"
    LOW = "low"


class Complex(Base):
    """단지 정보 테이블"""

    __tablename__ = "complexes"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False, comment="단지명")
    address = Column(String(500), nullable=False, comment="주소")
    region_code = Column(String(20), nullable=True, index=True, comment="시군구코드 (5자리)")

    # 법정동 (KB API 응답의 법정동코드/법정동명)
    dong_code = Column(String(10), nullable=True, index=True, comment="법정동코드 (10자리)")
    dong_name = Column(String(50), nullable=True, comment="법정동명")

    # KB 소스 식별자
    kb_complex_id = Column(String(50), unique=True, nullable=True, comment="KB 단지 ID")

    # 단지 기본 정보 (KB API에서 수집)
    lat = Column(Float, nullable=True, comment="WGS84 위도 (단지 중심)")
    lng = Column(Float, nullable=True, comment="WGS84 경도")
    road_address = Column(String(500), nullable=True, comment="도로명주소")
    total_households = Column(Integer, nullable=True, comment="총세대수")
    total_buildings = Column(Integer, nullable=True, comment="총동수")
    max_floor = Column(Integer, nullable=True, comment="최고층수")
    built_year = Column(String(10), nullable=True, comment="준공년월 (YYYY.MM)")
    total_parking = Column(Integer, nullable=True, comment="총주차대수")
    hallway_type = Column(String(50), nullable=True, comment="현관구조 (계단식/복도식)")
    heating_type = Column(String(50), nullable=True, comment="난방방식")
    builder = Column(String(200), nullable=True, comment="시공사")

    # 수집 설정
    priority = Column(Enum(PriorityLevel), default=PriorityLevel.NORMAL, comment="수집 우선순위")
    is_active = Column(Boolean, default=True, comment="수집 활성화 여부")
    collect_listings = Column(Boolean, default=True, comment="매물 수집 여부")
    
    # 메타데이터
    created_at = Column(DateTime, default=now_kst)
    updated_at = Column(DateTime, default=now_kst, onupdate=now_kst)
    
    # Relationships
    areas = relationship("Area", back_populates="complex", cascade="all, delete-orphan")
    kb_prices = relationship("KBPrice", back_populates="complex", cascade="all, delete-orphan")
    transactions = relationship("Transaction", back_populates="complex", cascade="all, delete-orphan")
    listings = relationship("Listing", back_populates="complex", cascade="all, delete-orphan")


class Area(Base):
    """단지 내 면적 타입"""

    __tablename__ = "areas"

    id = Column(Integer, primary_key=True, index=True)
    complex_id = Column(Integer, ForeignKey("complexes.id"), nullable=False)
    
    # 면적 정보
    exclusive_m2 = Column(Float, nullable=False, comment="전용면적(㎡)")
    supply_m2 = Column(Float, nullable=True, comment="공급면적(㎡)")
    pyeong = Column(Float, nullable=True, comment="평형")
    
    # KB 소스 식별자
    kb_area_code = Column(String(50), nullable=True, comment="KB 면적 코드")
    
    # 메타데이터
    created_at = Column(DateTime, default=now_kst)
    updated_at = Column(DateTime, default=now_kst, onupdate=now_kst)
    
    # Relationships
    complex = relationship("Complex", back_populates="areas")
    kb_prices = relationship("KBPrice", back_populates="area", cascade="all, delete-orphan")
