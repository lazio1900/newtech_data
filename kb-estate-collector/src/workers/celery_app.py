import logging

from celery import Celery
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
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
    # RedBeat — schedule 변경 즉시 반영
    beat_scheduler="redbeat.RedBeatScheduler",
    redbeat_redis_url=settings.celery_broker_url,
    redbeat_lock_timeout=900,
    beat_max_loop_interval=15,  # 15초마다 redis 폴링
)

# Auto-discover tasks
celery_app.autodiscover_tasks(['src.workers'])

# 정적 beat schedule (사용자 정의 cron 은 RedBeat 에 동적 등록되지만,
# zombie cleanup 같은 시스템 task 는 코드로 고정)
celery_app.conf.beat_schedule = {
    "cleanup-zombie-runs": {
        "task": "src.workers.tasks.cleanup_zombie_runs",
        "schedule": 300.0,  # 5분마다
    },
}


# Worker signal handlers for browser cleanup
from celery.signals import worker_shutdown
import logging

_logger = logging.getLogger(__name__)


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
