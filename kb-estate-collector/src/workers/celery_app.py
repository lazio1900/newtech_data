import logging

from celery import Celery
from celery.schedules import crontab
from celery.signals import worker_shutdown

from src.core.config import settings

_logger = logging.getLogger(__name__)

# Initialize Celery app
celery_app = Celery(
    "kb_estate_collector",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

# Celery configuration — RedBeat scheduler (redis 기반 동적 schedule)
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="Asia/Seoul",
    enable_utc=False,
    task_track_started=True,
    task_time_limit=3600,
    task_soft_time_limit=3000,
    worker_prefetch_multiplier=4,
    worker_max_tasks_per_child=1000,
    # ack 를 task 완료 후로 미뤄 worker cold shutdown 시 task 손실 방지.
    # 모든 task 는 멱등하게 작성되어 있어 (UPSERT / on_conflict_do_nothing) 재실행 안전.
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    # RedBeat — schedule 변경 즉시 반영
    beat_scheduler="redbeat.RedBeatScheduler",
    redbeat_redis_url=settings.celery_broker_url,
    redbeat_lock_timeout=900,
    beat_max_loop_interval=15,  # 15초마다 redis 폴링
)

# Auto-discover tasks
celery_app.autodiscover_tasks(["src.workers"])

# 큐 분리: 느린 listing 을 빠른 price/tx 와 격리해 head-of-line blocking 제거.
#   dispatch  — fan-out 디스패처 (run_kb_collection/run_region_collection/run_scheduled_job)
#   prepare   — 단지 prepare (detail/facility/area ensure + child enqueue)
#   fast      — price/transaction/molit (가볍고 빠름)
#   slow      — listing (매물, transient 백오프로 단지당 최대 17초)
# 미지정 task(cleanup_zombie_runs/discover/backfill)는 기본 'celery' 큐.
celery_app.conf.task_routes = {
    "src.workers.tasks.run_kb_collection": {"queue": "dispatch"},
    "src.workers.tasks.run_region_collection": {"queue": "dispatch"},
    "src.workers.tasks.run_scheduled_job": {"queue": "dispatch"},
    "src.workers.tasks.prepare_complex_task": {"queue": "prepare"},
    "src.workers.tasks.collect_kb_price_task": {"queue": "fast"},
    "src.workers.tasks.collect_kb_transaction_task": {"queue": "fast"},
    "src.workers.tasks.collect_molit_transaction_task": {"queue": "fast"},
    "src.workers.tasks.collect_kb_listing_task": {"queue": "slow"},
}

# 정적 beat schedule (사용자 정의 cron 은 RedBeat 에 동적 등록되지만,
# zombie cleanup 같은 시스템 task 는 코드로 고정)
celery_app.conf.beat_schedule = {
    "cleanup-zombie-runs": {
        "task": "src.workers.tasks.cleanup_zombie_runs",
        "schedule": 300.0,  # 5분마다
    },
    # 주간 단지 발견 — 활성 잡 지역의 신규 아파트를 자동 등록.
    # 일 20:00 KST: 가격 잡(01·05·10·13시)과 겹치지 않고 다음 수집 사이클 직전.
    "discover-active-regions": {
        "task": "src.workers.tasks.discover_active_regions",
        "schedule": crontab(hour=20, minute=0, day_of_week=0),
    },
}


# Worker signal handlers for browser cleanup
@worker_shutdown.connect
def on_worker_shutdown(**kwargs):
    """워커 종료 시 브라우저 세션 정리"""
    import asyncio

    try:
        from src.browser.session_manager import BrowserSessionManager

        loop = asyncio.new_event_loop()
        loop.run_until_complete(BrowserSessionManager.shutdown())
        loop.close()
        _logger.info("Browser sessions cleaned up on worker shutdown")
    except Exception as e:
        _logger.warning(f"Browser cleanup on shutdown failed: {e}")
