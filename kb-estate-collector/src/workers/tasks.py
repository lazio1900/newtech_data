from datetime import datetime
from typing import Dict, Any
import logging
from celery import Task
from sqlalchemy.orm import Session

from src.workers.celery_app import celery_app
from src.core.database import SessionLocal
from src.models import CrawlRun, CrawlTask, Complex, Area, KBPrice, RunStatus, TaskStatus
from src.connectors import KBPriceConnector, KBListingConnector, MolitTransactionConnector

logger = logging.getLogger(__name__)


class DatabaseTask(Task):
    """Base task with database session management"""
    
    _db: Session = None
    
    @property
    def db(self):
        if self._db is None:
            self._db = SessionLocal()
        return self._db
    
    def after_return(self, *args, **kwargs):
        if self._db is not None:
            self._db.close()
            self._db = None


@celery_app.task(base=DatabaseTask, bind=True, max_retries=3)
def collect_kb_price_task(
    self,
    run_id: int,
    complex_id: int,
    area_id: int,
) -> Dict[str, Any]:
    """
    단일 단지/면적에 대한 KB 시세 수집 태스크
    """
    db = self.db
    task_key = f"kb_price_{complex_id}_{area_id}"
    
    # Create task record
    task_record = CrawlTask(
        run_id=run_id,
        task_key=task_key,
        status=TaskStatus.RUNNING,
        started_at=datetime.utcnow(),
    )
    db.add(task_record)
    db.commit()
    
    try:
        # Collect data
        connector = KBPriceConnector()
        result = connector.collect(complex_id=complex_id, area_id=area_id)
        
        # Save to database
        for item in result['items']:
            kb_price = KBPrice(
                complex_id=complex_id,
                area_id=area_id,
                as_of_date=item['as_of_date'],
                general_price=item['general_price'],
                high_avg_price=item['high_avg_price'],
                low_avg_price=item['low_avg_price'],
                source=item['source'],
                fetched_at=datetime.utcnow(),
                parser_version=item.get('parser_version'),
            )
            db.merge(kb_price)  # Use merge to handle duplicates
        
        db.commit()
        
        # Update task record
        task_record.status = TaskStatus.SUCCESS
        task_record.finished_at = datetime.utcnow()
        task_record.items_collected = len(result['items'])
        task_record.items_saved = len(result['items'])
        db.commit()
        
        logger.info(f"Task {task_key} completed: {len(result['items'])} items")
        
        return {
            'status': 'success',
            'items_collected': len(result['items']),
        }
    
    except Exception as e:
        logger.exception(f"Task {task_key} failed: {e}")
        
        task_record.status = TaskStatus.FAILED
        task_record.finished_at = datetime.utcnow()
        task_record.error_type = type(e).__name__
        task_record.error_message = str(e)
        db.commit()
        
        # Retry
        raise self.retry(exc=e, countdown=60 * (2 ** self.request.retries))


@celery_app.task(base=DatabaseTask, bind=True)
def run_kb_price_collection(self, job_id: int = None) -> Dict[str, Any]:
    """
    KB 시세 수집 작업 실행 (모든 활성 단지)
    """
    db = self.db
    
    # Create run record
    run = CrawlRun(
        job_id=job_id,
        status=RunStatus.RUNNING,
        started_at=datetime.utcnow(),
    )
    db.add(run)
    db.commit()
    
    try:
        # Get active complexes and areas
        complexes = db.query(Complex).filter(Complex.is_active == True).all()
        
        tasks = []
        for complex in complexes:
            for area in complex.areas:
                # Launch task for each complex/area
                task = collect_kb_price_task.delay(
                    run_id=run.id,
                    complex_id=complex.id,
                    area_id=area.id,
                )
                tasks.append(task)
        
        run.total_tasks = len(tasks)
        db.commit()
        
        logger.info(f"Run {run.id}: Launched {len(tasks)} tasks")
        
        return {
            'run_id': run.id,
            'total_tasks': len(tasks),
        }
    
    except Exception as e:
        logger.exception(f"Run {run.id} failed: {e}")
        run.status = RunStatus.FAILED
        run.finished_at = datetime.utcnow()
        db.commit()
        raise


@celery_app.task(base=DatabaseTask, bind=True)
def run_transaction_collection(self, job_id: int = None) -> Dict[str, Any]:
    """
    실거래가 수집 작업 실행
    (실제 구현에서는 지역/기간별로 분할)
    """
    logger.info("Transaction collection task placeholder")
    return {'status': 'not_implemented'}


@celery_app.task(base=DatabaseTask, bind=True)
def run_listing_collection(self, job_id: int = None) -> Dict[str, Any]:
    """
    매물/호가 수집 작업 실행
    """
    logger.info("Listing collection task placeholder")
    return {'status': 'not_implemented'}
