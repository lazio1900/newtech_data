from datetime import datetime
from sqlalchemy import Column, Integer, String, DateTime, Text, Enum, ForeignKey, Index, Boolean
from sqlalchemy.orm import relationship
import enum
from src.core.database import Base


class JobType(str, enum.Enum):
    """수집 작업 유형"""
    KB_PRICE = "kb_price"
    KB_LISTING = "kb_listing"
    MOLIT_TRANSACTION = "molit_transaction"


class JobStatus(str, enum.Enum):
    """작업 상태"""
    ACTIVE = "active"
    PAUSED = "paused"
    DISABLED = "disabled"


class RunStatus(str, enum.Enum):
    """실행 상태"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    PARTIAL = "partial"
    FAILED = "failed"
    CANCELLED = "cancelled"


class TaskStatus(str, enum.Enum):
    """태스크 상태"""
    PENDING = "pending"
    RUNNING = "running"
    SUCCESS = "success"
    FAILED = "failed"
    RETRY = "retry"
    SKIPPED = "skipped"


class CrawlJob(Base):
    """수집 작업 정의"""

    __tablename__ = "crawl_jobs"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(200), nullable=False, unique=True, comment="작업명")
    job_type = Column(Enum(JobType), nullable=False, comment="작업 유형")
    description = Column(Text, nullable=True, comment="설명")
    
    # 대상 설정
    target_config = Column(Text, nullable=True, comment="대상 설정 (JSON)")
    
    # 스케줄
    cron_schedule = Column(String(100), nullable=True, comment="Cron 스케줄")
    
    # 동시성 및 레이트 제한
    max_concurrency = Column(Integer, default=5, comment="최대 동시 처리 수")
    rate_limit_per_minute = Column(Integer, default=60, comment="분당 요청 제한")
    
    # 상태
    status = Column(Enum(JobStatus), default=JobStatus.ACTIVE, comment="작업 상태")
    
    # 메타데이터
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    created_by = Column(String(100), nullable=True, comment="생성자")
    
    # Relationships
    runs = relationship("CrawlRun", back_populates="job", cascade="all, delete-orphan")


class CrawlRun(Base):
    """수집 실행 이력"""

    __tablename__ = "crawl_runs"

    id = Column(Integer, primary_key=True, index=True)
    job_id = Column(Integer, ForeignKey("crawl_jobs.id"), nullable=False)
    
    # 실행 정보
    status = Column(Enum(RunStatus), default=RunStatus.PENDING, comment="실행 상태")
    started_at = Column(DateTime, nullable=True, comment="시작 시각")
    finished_at = Column(DateTime, nullable=True, comment="종료 시각")
    
    # 통계
    total_tasks = Column(Integer, default=0, comment="총 태스크 수")
    success_count = Column(Integer, default=0, comment="성공 건수")
    failed_count = Column(Integer, default=0, comment="실패 건수")
    skipped_count = Column(Integer, default=0, comment="스킵 건수")
    
    # 에러 정보
    error_summary = Column(Text, nullable=True, comment="에러 요약 (JSON)")
    
    # 품질 지표
    quality_warnings = Column(Text, nullable=True, comment="품질 경고 (JSON)")
    
    # 메타데이터
    created_at = Column(DateTime, default=datetime.utcnow)
    triggered_by = Column(String(100), nullable=True, comment="실행 트리거 (user/schedule)")
    
    # Relationships
    job = relationship("CrawlJob", back_populates="runs")
    tasks = relationship("CrawlTask", back_populates="run", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index("idx_run_job_status", "job_id", "status"),
        Index("idx_run_started", "started_at"),
    )


class CrawlTask(Base):
    """개별 수집 태스크"""

    __tablename__ = "crawl_tasks"

    id = Column(Integer, primary_key=True, index=True)
    run_id = Column(Integer, ForeignKey("crawl_runs.id"), nullable=False)
    
    # 태스크 정보
    task_key = Column(String(200), nullable=False, comment="태스크 키 (complex_id, area_id 등)")
    status = Column(Enum(TaskStatus), default=TaskStatus.PENDING, comment="태스크 상태")
    
    # 실행 정보
    started_at = Column(DateTime, nullable=True)
    finished_at = Column(DateTime, nullable=True)
    retry_count = Column(Integer, default=0, comment="재시도 횟수")
    
    # 에러 정보
    error_type = Column(String(100), nullable=True, comment="에러 유형")
    error_message = Column(Text, nullable=True, comment="에러 메시지")
    error_traceback = Column(Text, nullable=True, comment="에러 스택")
    
    # 결과
    items_collected = Column(Integer, default=0, comment="수집 건수")
    items_saved = Column(Integer, default=0, comment="저장 건수")
    
    # 메타데이터
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    run = relationship("CrawlRun", back_populates="tasks")
    raw_payloads = relationship("RawPayload", back_populates="task", cascade="all, delete-orphan")
    
    __table_args__ = (
        Index("idx_task_run_status", "run_id", "status"),
        Index("idx_task_key", "task_key"),
    )


class RawPayload(Base):
    """원문 데이터 스냅샷 (재현성/감사)"""

    __tablename__ = "raw_payloads"

    id = Column(Integer, primary_key=True, index=True)
    task_id = Column(Integer, ForeignKey("crawl_tasks.id"), nullable=False)
    
    # 원문 정보
    payload_type = Column(String(50), nullable=False, comment="payload 유형 (json/html)")
    content_hash = Column(String(64), nullable=False, comment="콘텐츠 해시")
    
    # 저장 위치
    storage_path = Column(String(500), nullable=True, comment="저장 경로 (S3 등)")
    inline_content = Column(Text, nullable=True, comment="인라인 저장 (작은 경우)")
    
    # 메타데이터
    size_bytes = Column(Integer, nullable=True, comment="크기 (바이트)")
    compressed = Column(Boolean, default=False, comment="압축 여부")
    
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # Relationships
    task = relationship("CrawlTask", back_populates="raw_payloads")
    
    __table_args__ = (
        Index("idx_payload_hash", "content_hash"),
        Index("idx_payload_created", "created_at"),
    )
