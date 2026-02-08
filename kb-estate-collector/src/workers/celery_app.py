from celery import Celery
from src.core.config import settings

# Initialize Celery app
celery_app = Celery(
    "kb_estate_collector",
    broker=settings.celery_broker_url,
    backend=settings.celery_result_backend,
)

# Celery configuration
celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
    task_track_started=True,
    task_time_limit=3600,  # 1 hour
    task_soft_time_limit=3000,  # 50 minutes
    worker_prefetch_multiplier=1,
    worker_max_tasks_per_child=1000,
)

# Beat schedule for periodic tasks
celery_app.conf.beat_schedule = {
    'collect-kb-prices-daily': {
        'task': 'src.workers.tasks.run_kb_price_collection',
        'schedule': 86400.0,  # Daily (24 hours)
    },
    'collect-transactions-daily': {
        'task': 'src.workers.tasks.run_transaction_collection',
        'schedule': 86400.0,  # Daily
    },
}

# Auto-discover tasks
celery_app.autodiscover_tasks(['src.workers'])
