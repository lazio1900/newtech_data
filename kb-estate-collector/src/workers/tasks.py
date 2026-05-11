"""
Celery 태스크 정의.

KB부동산 데이터 수집 태스크:
- KB 시세 수집 (단지/면적별)
- KB 실거래가 수집 (단지별)
- KB 매물 수집 (단지별)
- 지역 기반 단지 발견
- 지역 기반 전체 수집
"""
import asyncio
import json
import logging
from typing import Any, Dict, List, Optional

from celery import Task
from sqlalchemy.orm import Session

from src.connectors import KBListingConnector, KBPriceConnector, KBTransactionConnector
from src.core.database import SessionLocal
from src.core.time import now_kst
from src.models import (
    Area,
    Complex,
    ComplexFacility,
    CrawlRun,
    CrawlTask,
    KBPrice,
    Listing,
    ListingStatus,
    RunStatus,
    TaskStatus,
    Transaction,
)
from src.workers.celery_app import celery_app

logger = logging.getLogger(__name__)


def run_async(coro):
    """async 코루틴을 동기적으로 실행하는 헬퍼."""
    loop = asyncio.new_event_loop()
    try:
        return loop.run_until_complete(coro)
    finally:
        loop.close()


def ensure_complex_detail(db: Session, complex_obj: Complex):
    """
    단지 기본 정보가 없으면 KB API에서 조회하여 업데이트.
    (세대수, 동수, 최고층수, 준공년월, 주차대수, 현관구조, 주소, 법정동 등)
    """
    # 이미 핵심 정보(세대수)와 법정동코드가 모두 채워졌으면 스킵
    if complex_obj.total_households and complex_obj.dong_code:
        return

    if not complex_obj.kb_complex_id:
        return

    try:
        from src.connectors.kb_endpoints import COMPLEX_DETAIL
        from src.services.complex_discovery import _DiscoveryConnector

        connector = _DiscoveryConnector(name="detail_fetch", rate_limit_per_minute=30)
        data = run_async(
            connector._fetch_via_http(
                COMPLEX_DETAIL,
                {"단지기본일련번호": complex_obj.kb_complex_id, "물건종류": "01"},
            )
        )

        body = data.get("dataBody", {}).get("data", {})
        if not body:
            return

        # 주소
        road_addr = body.get("신주소") or body.get("도로기본주소")
        old_addr = body.get("구주소")
        if road_addr:
            complex_obj.road_address = road_addr
        if old_addr and not complex_obj.address:
            complex_obj.address = old_addr

        # 기본 정보
        complex_obj.total_households = body.get("총세대수")
        complex_obj.total_buildings = body.get("총동수")
        complex_obj.max_floor = body.get("최고층수") or body.get("건물최고층수")
        complex_obj.total_parking = body.get("총주차대수")
        complex_obj.hallway_type = body.get("현관구조")
        complex_obj.heating_type = body.get("난방방식구분명")
        complex_obj.builder = body.get("시공사명")

        # 준공년월
        built = body.get("준공년월")
        if built:
            complex_obj.built_year = built

        # 법정동코드 + 동명 (KB API: '법정동코드', '읍면동명')
        dong_code = body.get("법정동코드") or body.get("dongCd")
        if dong_code:
            complex_obj.dong_code = str(dong_code)
        dong_name = body.get("읍면동명") or body.get("법정동명") or body.get("dongNm")
        if dong_name:
            complex_obj.dong_name = dong_name

        # 좌표 (시설 마커 endpoint 호출용)
        lat = body.get("wgs84위도")
        lng = body.get("wgs84경도")
        if lat:
            try:
                complex_obj.lat = float(lat)
            except (ValueError, TypeError):
                pass
        if lng:
            try:
                complex_obj.lng = float(lng)
            except (ValueError, TypeError):
                pass

        db.flush()
        logger.info(
            f"Complex {complex_obj.id} ({complex_obj.name}): "
            f"detail fetched - {complex_obj.total_households}세대, "
            f"{complex_obj.built_year} 준공, dong={complex_obj.dong_code or '-'}({complex_obj.dong_name or '-'})"
        )

    except Exception as e:
        logger.warning(f"Complex {complex_obj.id}: detail fetch failed: {e}")


# 학교과정별 거리 cutoff (m) — 너무 멀면 학군에 무의미
SCHOOL_DISTANCE_CUTOFF: Dict[str, int] = {
    "kindergarten": 500,
    "preschool": 500,
    "elementary": 1000,
    "middle": 2000,
    "high": 2000,
}


def ensure_complex_facilities(db: Session, complex_obj: Complex) -> int:
    """단지 주변 시설(학군/지하철/병원/공원)을 KB API + OSM 에서 수집해 저장.

    이미 facility 데이터가 있으면 스킵. 신규 단지 또는 facility 비어있는 단지만 수집.
    학교는 sub_type 별 거리 cutoff 적용 (어린이집/유치원 500m, 초 1km, 중/고 2km).
    반환: 저장된 facility row 수.
    """
    if not complex_obj.kb_complex_id:
        return 0

    # 좌표 기반 카테고리(subway/hospital/park) 가 하나라도 있으면 정상 수집된 것으로 간주.
    # 학군만 있는 경우(옛 코드 시점 잔재)는 보강 대상 — 학군까지 모두 비우고 재수집해
    # 거리 cutoff 도 재적용한다.
    has_coord_based = (
        db.query(ComplexFacility.id)
        .filter(
            ComplexFacility.complex_id == complex_obj.id,
            ComplexFacility.facility_type.in_(["subway", "hospital", "park"]),
        )
        .first()
    )
    if has_coord_based:
        return 0

    # 학군만 잔존하면 삭제 후 fetch_all 로 통합 재수집
    db.query(ComplexFacility).filter(ComplexFacility.complex_id == complex_obj.id).delete(
        synchronize_session=False
    )
    db.flush()

    try:
        from src.connectors.kb_facility import KBFacilityConnector

        connector = KBFacilityConnector(rate_limit_per_minute=30)
        items = run_async(
            connector.fetch_all(
                complex_obj.kb_complex_id,
                lat=complex_obj.lat,
                lng=complex_obj.lng,
            )
        )

        from sqlalchemy.dialects.postgresql import insert as pg_insert

        saved = 0
        skipped_far = 0
        now = now_kst()
        # KB/OSM 응답에 (complex_id, facility_type, external_id) 동일한 row 가
        # 중복 포함되는 경우가 있어 ON CONFLICT DO NOTHING 으로 안전 INSERT.
        for item in items:
            if item["facility_type"] == "school":
                cutoff = SCHOOL_DISTANCE_CUTOFF.get(item.get("sub_type") or "")
                if cutoff and item.get("distance_m") is not None and item["distance_m"] > cutoff:
                    skipped_far += 1
                    continue

            stmt = (
                pg_insert(ComplexFacility)
                .values(
                    complex_id=complex_obj.id,
                    facility_type=item["facility_type"],
                    sub_type=item.get("sub_type"),
                    external_id=item.get("external_id"),
                    name=item.get("name"),
                    address=item.get("address"),
                    phone=item.get("phone"),
                    distance_m=item.get("distance_m"),
                    lat=item.get("lat"),
                    lng=item.get("lng"),
                    meta=item.get("meta"),
                    fetched_at=now,
                )
                .on_conflict_do_nothing(
                    index_elements=["complex_id", "facility_type", "external_id"],
                )
            )
            res = db.execute(stmt)
            if res.rowcount and res.rowcount > 0:
                saved += 1

        db.flush()
        from collections import Counter

        cat = Counter(it["facility_type"] for it in items[: saved + skipped_far])
        logger.info(
            f"Complex {complex_obj.id} ({complex_obj.name}): facilities collected — "
            f"{dict(cat)} (saved={saved}, skipped_far={skipped_far})"
        )
        return saved
    except Exception as e:
        logger.warning(f"Complex {complex_obj.id}: facility fetch failed: {e}")
        return 0


def ensure_complex_areas(db: Session, complex_obj: Complex) -> List[Area]:
    """
    단지에 면적 정보가 없으면 KB API에서 조회하여 자동 등록.
    지역 발견 시 면적 정보 없이 등록된 단지를 위한 보완 로직.
    """
    if complex_obj.areas:
        return complex_obj.areas

    if not complex_obj.kb_complex_id:
        logger.warning(
            f"Complex {complex_obj.id} ({complex_obj.name}): no kb_complex_id, skip area fetch"
        )
        return []

    logger.info(f"Complex {complex_obj.id} ({complex_obj.name}): fetching areas from KB API")

    try:
        from src.connectors.kb_endpoints import COMPLEX_TYPE_INFO
        from src.services.complex_discovery import _DiscoveryConnector

        connector = _DiscoveryConnector(name="area_fetch", rate_limit_per_minute=30)
        data = run_async(
            connector._fetch_via_http(
                COMPLEX_TYPE_INFO, {"단지기본일련번호": complex_obj.kb_complex_id}
            )
        )

        body = data.get("dataBody", {}).get("data", [])
        area_list = body if isinstance(body, list) else []

        created = []
        for a in area_list:
            exclusive = a.get("전용면적", 0)
            try:
                exclusive = float(str(exclusive).replace(",", ""))
            except (ValueError, TypeError):
                continue
            if exclusive <= 0:
                continue

            supply = None
            try:
                supply = float(str(a.get("공급면적", "")).replace(",", "")) or None
            except (ValueError, TypeError):
                pass

            pyeong = None
            try:
                pyeong = float(str(a.get("평", "")).replace(",", "")) or None
            except (ValueError, TypeError):
                pass

            area_code = str(a.get("면적일련번호", "")) or None

            area = Area(
                complex_id=complex_obj.id,
                exclusive_m2=exclusive,
                supply_m2=supply,
                pyeong=pyeong,
                kb_area_code=area_code,
            )
            db.add(area)
            created.append(area)

        if created:
            db.flush()
            logger.info(f"Complex {complex_obj.id}: registered {len(created)} areas")
        else:
            logger.warning(f"Complex {complex_obj.id}: no valid areas from KB API")

        return created

    except Exception as e:
        logger.warning(f"Complex {complex_obj.id}: area fetch failed: {e}")
        return []


def _get_target_complexes(db: Session, target_config: Optional[str] = None) -> List[Complex]:
    """
    target_config에서 대상 단지 목록을 결정.
    - complex_ids가 있으면 해당 단지만 (활성 여부 무관)
    - 없으면 모든 활성 단지
    """
    if target_config:
        try:
            config = json.loads(target_config)
        except (json.JSONDecodeError, TypeError):
            config = {}

        complex_ids = config.get("complex_ids")
        if complex_ids and isinstance(complex_ids, list):
            return db.query(Complex).filter(Complex.id.in_(complex_ids)).all()

    return db.query(Complex).filter(Complex.is_active == True).all()


def _finalize_run_if_complete(db: Session, run_id: int):
    """
    Run에 속한 모든 태스크가 완료(success/failed/skipped)되었는지 확인하고,
    모두 끝났으면 Run 상태를 성공/실패/부분성공으로 갱신.
    """
    run = db.query(CrawlRun).filter(CrawlRun.id == run_id).first()
    if not run or run.status not in (RunStatus.RUNNING,):
        return

    total = run.total_tasks or 0
    if total == 0:
        return

    finished_statuses = {TaskStatus.SUCCESS, TaskStatus.FAILED, TaskStatus.SKIPPED}
    tasks = db.query(CrawlTask).filter(CrawlTask.run_id == run_id).all()
    finished = [t for t in tasks if t.status in finished_statuses]

    if len(finished) < total:
        return  # 아직 진행 중

    success = sum(1 for t in finished if t.status == TaskStatus.SUCCESS)
    failed = sum(1 for t in finished if t.status == TaskStatus.FAILED)
    skipped = sum(1 for t in finished if t.status == TaskStatus.SKIPPED)

    run.success_count = success
    run.failed_count = failed
    run.skipped_count = skipped
    run.finished_at = now_kst()

    if failed == 0:
        run.status = RunStatus.SUCCESS
    elif success == 0:
        run.status = RunStatus.FAILED
    else:
        run.status = RunStatus.PARTIAL

    db.commit()
    logger.info(
        f"Run {run_id} finalized: {run.status.value} "
        f"(success={success}, failed={failed}, skipped={skipped})"
    )


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


# =============================================================================
# KB 시세 수집
# =============================================================================


@celery_app.task(base=DatabaseTask, bind=True)
def collect_kb_price_task(
    self,
    run_id: int,
    complex_id: int,
    area_id: int,
) -> Dict[str, Any]:
    """단일 단지/면적에 대한 KB 시세 수집 태스크"""
    db = self.db
    task_key = f"kb_price_{complex_id}_{area_id}"

    task_record = CrawlTask(
        run_id=run_id,
        task_key=task_key,
        status=TaskStatus.RUNNING,
        started_at=now_kst(),
    )
    db.add(task_record)
    db.commit()

    try:
        connector = KBPriceConnector(db_session=db)
        result = connector.collect(complex_id=complex_id, area_id=area_id)

        items_saved = 0
        for item in result["items"]:
            existing = (
                db.query(KBPrice)
                .filter(
                    KBPrice.complex_id == complex_id,
                    KBPrice.area_id == area_id,
                    KBPrice.as_of_date == item["as_of_date"],
                )
                .first()
            )

            if existing:
                existing.general_price = item["general_price"]
                existing.high_avg_price = item["high_avg_price"]
                existing.low_avg_price = item["low_avg_price"]
                existing.fetched_at = now_kst()
                existing.parser_version = item.get("parser_version")
            else:
                db.add(
                    KBPrice(
                        complex_id=complex_id,
                        area_id=area_id,
                        as_of_date=item["as_of_date"],
                        general_price=item["general_price"],
                        high_avg_price=item["high_avg_price"],
                        low_avg_price=item["low_avg_price"],
                        source=item["source"],
                        fetched_at=now_kst(),
                        parser_version=item.get("parser_version"),
                    )
                )
            items_saved += 1

        # 최근실거래가 추출 (BasePrcInfoNew 응답에 포함)
        raw_data = result.get("raw")
        if raw_data:
            area_obj = db.get(Area, area_id)
            exclusive_m2 = area_obj.exclusive_m2 if area_obj and area_obj.exclusive_m2 else None

            tx_data = connector.parse_recent_transaction(raw_data)
            if tx_data and exclusive_m2 is not None:
                existing_tx = (
                    db.query(Transaction)
                    .filter(
                        Transaction.complex_id == complex_id,
                        Transaction.contract_date == tx_data["contract_date"],
                        Transaction.price == tx_data["price"],
                        Transaction.exclusive_m2 == exclusive_m2,
                    )
                    .first()
                )
                if not existing_tx:
                    db.add(
                        Transaction(
                            complex_id=complex_id,
                            contract_date=tx_data["contract_date"],
                            price=tx_data["price"],
                            exclusive_m2=exclusive_m2,
                            floor=tx_data.get("floor"),
                            source="kb",
                            fetched_at=now_kst(),
                        )
                    )
                    items_saved += 1

        db.commit()
        task_record.status = TaskStatus.SUCCESS
        task_record.items_collected = len(result["items"])
        task_record.items_saved = items_saved
        logger.info(
            f"Task {task_key} completed: {len(result['items'])} prices, {items_saved} total saved"
        )
        return {"status": "success", "items_collected": len(result["items"])}

    except BaseException as e:
        logger.exception(f"Task {task_key} failed: {e}")
        try:
            db.rollback()
        except Exception:
            pass
        task_record.status = TaskStatus.FAILED
        task_record.error_type = type(e).__name__
        task_record.error_message = str(e)[:500]
        return {"status": "failed", "error": str(e)}

    finally:
        task_record.finished_at = now_kst()
        try:
            db.commit()
        except Exception:
            pass
        _finalize_run_if_complete(db, run_id)


# =============================================================================
# KB 실거래가 수집
# =============================================================================


@celery_app.task(base=DatabaseTask, bind=True)
def collect_kb_transaction_task(
    self,
    run_id: int,
    complex_id: int,
    area_id: Optional[int] = None,
) -> Dict[str, Any]:
    """단일 단지(면적)에 대한 KB 실거래가 수집. preSalePrices 사용."""
    db = self.db
    task_key = f"kb_transaction_{complex_id}_{area_id or 'all'}"

    task_record = CrawlTask(
        run_id=run_id,
        task_key=task_key,
        status=TaskStatus.RUNNING,
        started_at=now_kst(),
    )
    db.add(task_record)
    db.commit()

    try:
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        connector = KBTransactionConnector(db_session=db)
        result = connector.collect(complex_id=complex_id, area_id=area_id)

        saved_count = 0
        for item in result["items"]:
            # idx_transaction_unique 제약 — 동일 거래 중복 INSERT 방지
            stmt = (
                pg_insert(Transaction)
                .values(
                    complex_id=complex_id,
                    contract_date=item["contract_date"],
                    price=item["price"],
                    exclusive_m2=item["exclusive_m2"],
                    floor=item.get("floor"),
                    is_cancelled=item.get("is_cancelled", False),
                    source="kb",
                    source_id=item.get("external_id"),
                    fetched_at=now_kst(),
                )
                .on_conflict_do_nothing(
                    index_elements=[
                        "complex_id",
                        "contract_date",
                        "price",
                        "exclusive_m2",
                        "floor",
                    ]
                )
            )
            res = db.execute(stmt)
            if res.rowcount and res.rowcount > 0:
                saved_count += 1

        db.commit()
        task_record.status = TaskStatus.SUCCESS
        task_record.items_collected = len(result["items"])
        task_record.items_saved = saved_count
        logger.info(f"Task {task_key} completed: {len(result['items'])} items")
        return {"status": "success", "items_collected": len(result["items"])}

    except BaseException as e:
        logger.exception(f"Task {task_key} failed: {e}")
        try:
            db.rollback()
        except Exception:
            pass
        task_record.status = TaskStatus.FAILED
        task_record.error_type = type(e).__name__
        task_record.error_message = str(e)[:500]
        return {"status": "failed", "error": str(e)}

    finally:
        task_record.finished_at = now_kst()
        try:
            db.commit()
        except Exception:
            pass
        _finalize_run_if_complete(db, run_id)


# =============================================================================
# KB 매물 수집
# =============================================================================


@celery_app.task(base=DatabaseTask, bind=True)
def collect_kb_listing_task(
    self,
    run_id: int,
    complex_id: int,
) -> Dict[str, Any]:
    """단일 단지에 대한 KB 매물 수집 태스크"""
    db = self.db
    task_key = f"kb_listing_{complex_id}"

    task_record = CrawlTask(
        run_id=run_id,
        task_key=task_key,
        status=TaskStatus.RUNNING,
        started_at=now_kst(),
    )
    db.add(task_record)
    db.commit()

    try:
        connector = KBListingConnector(db_session=db)
        result = connector.collect(complex_id=complex_id)

        saved_count = 0
        seen_ids = set()

        for item in result["items"]:
            listing_id = item["source_listing_id"]
            seen_ids.add(listing_id)

            existing = db.query(Listing).filter(Listing.source_listing_id == listing_id).first()

            if existing:
                existing.ask_price = item["ask_price"]
                existing.status = ListingStatus.ACTIVE
                existing.fetched_at = now_kst()
                existing.last_seen_at = now_kst()
            else:
                listing = Listing(
                    complex_id=complex_id,
                    source_listing_id=listing_id,
                    ask_price=item["ask_price"],
                    exclusive_m2=item.get("exclusive_m2"),
                    floor=item.get("floor"),
                    status=ListingStatus.ACTIVE,
                    posted_at=item.get("posted_at"),
                    source="kb",
                    fetched_at=now_kst(),
                    last_seen_at=now_kst(),
                )
                db.add(listing)
            saved_count += 1

        # 이번에 안 보인 기존 ACTIVE 매물 → REMOVED
        if seen_ids:
            stale_listings = (
                db.query(Listing)
                .filter(
                    Listing.complex_id == complex_id,
                    Listing.status == ListingStatus.ACTIVE,
                    Listing.source_listing_id.notin_(seen_ids),
                )
                .all()
            )
            for stale in stale_listings:
                stale.status = ListingStatus.REMOVED
                stale.status_updated_at = now_kst()

        db.commit()
        task_record.status = TaskStatus.SUCCESS
        task_record.items_collected = len(result["items"])
        task_record.items_saved = saved_count
        logger.info(f"Task {task_key} completed: {len(result['items'])} items")
        return {"status": "success", "items_collected": len(result["items"])}

    except BaseException as e:
        logger.exception(f"Task {task_key} failed: {e}")
        try:
            db.rollback()
        except Exception:
            pass
        task_record.status = TaskStatus.FAILED
        task_record.error_type = type(e).__name__
        task_record.error_message = str(e)[:500]
        return {"status": "failed", "error": str(e)}

    finally:
        task_record.finished_at = now_kst()
        try:
            db.commit()
        except Exception:
            pass
        _finalize_run_if_complete(db, run_id)


# =============================================================================
# KB 통합 수집 (시세 + 최근실거래가)
# =============================================================================


@celery_app.task(base=DatabaseTask, bind=True)
def run_kb_collection(
    self,
    job_id: int = None,
    run_id: int = None,
    target_config: str = None,
) -> Dict[str, Any]:
    """
    KB 데이터 통합 수집.
    각 단지마다 시세(면적별) 수집 — BasePrcInfoNew에서 시세 + 최근실거래가 동시 추출.
    """
    db = self.db

    if run_id:
        run = db.query(CrawlRun).filter(CrawlRun.id == run_id).first()
        run.status = RunStatus.RUNNING
        run.started_at = now_kst()
    else:
        run = CrawlRun(
            job_id=job_id,
            status=RunStatus.RUNNING,
            started_at=now_kst(),
        )
        db.add(run)
    db.commit()

    # target_config가 없으면 job에서 가져오기
    if not target_config and job_id:
        from src.models import CrawlJob

        j = db.query(CrawlJob).filter(CrawlJob.id == job_id).first()
        if j:
            target_config = j.target_config

    try:
        complexes = _get_target_complexes(db, target_config)

        total_tasks = 0
        for complex_obj in complexes:
            # 단지 기본 정보 수집 (세대수, 년식, 주소 등)
            ensure_complex_detail(db, complex_obj)

            # 단지 주변 학군 수집 (이미 있으면 스킵)
            ensure_complex_facilities(db, complex_obj)

            # 면적이 없으면 KB API에서 자동 조회
            areas = complex_obj.areas or ensure_complex_areas(db, complex_obj)

            # 자식 collect_* 태스크는 다른 prefork worker가 즉시 픽업한다.
            # ensure_* 가 만든 row를 자식 트랜잭션에서 보려면 enqueue 전 commit 필수.
            db.commit()

            # 시세 + 실거래가 (면적별)
            for area in areas:
                collect_kb_price_task.delay(
                    run_id=run.id,
                    complex_id=complex_obj.id,
                    area_id=area.id,
                )
                total_tasks += 1
                collect_kb_transaction_task.delay(
                    run_id=run.id,
                    complex_id=complex_obj.id,
                    area_id=area.id,
                )
                total_tasks += 1

            # 매물 수집 (단지별)
            collect_kb_listing_task.delay(
                run_id=run.id,
                complex_id=complex_obj.id,
            )
            total_tasks += 1

        db.commit()
        run.total_tasks = total_tasks
        db.commit()

        logger.info(f"Run {run.id}: Launched {total_tasks} tasks for {len(complexes)} complexes")
        return {"run_id": run.id, "total_tasks": total_tasks, "complexes_count": len(complexes)}

    except Exception as e:
        logger.exception(f"Run {run.id} failed: {e}")
        run.status = RunStatus.FAILED
        run.finished_at = now_kst()
        db.commit()
        raise


# =============================================================================
# 지역 기반 단지 발견 / 전체 수집
# =============================================================================


@celery_app.task(base=DatabaseTask, bind=True)
def discover_complexes_task(self, region_code: str) -> Dict[str, Any]:
    """지역코드로 아파트 단지 자동 발견 및 DB 등록"""
    from src.services.complex_discovery import ComplexDiscoveryService

    db = self.db
    service = ComplexDiscoveryService(db)
    result = run_async(service.discover_complexes(region_code))

    logger.info(
        f"Discovery for region {region_code}: "
        f"{result['new_registered']} new, {result['already_exists']} existing"
    )
    return result


@celery_app.task(base=DatabaseTask, bind=True)
def run_region_collection(
    self,
    region_code: str,
    job_id: int = None,
    run_id: int = None,
) -> Dict[str, Any]:
    """
    지역 기반 전체 수집:
    1. 단지 발견 (미등록 단지 자동 추가)
    2. 시세 수집 (단지별/면적별) — BasePrcInfoNew에서 시세 + 최근실거래가 동시 추출
    """
    db = self.db

    # 기존 run 사용 또는 신규 생성
    if run_id:
        run = db.query(CrawlRun).filter(CrawlRun.id == run_id).first()
        run.status = RunStatus.RUNNING
    else:
        run = CrawlRun(
            job_id=job_id,
            status=RunStatus.RUNNING,
            started_at=now_kst(),
        )
        db.add(run)
    db.commit()

    # Step 1: 단지 발견
    from src.services.complex_discovery import ComplexDiscoveryService

    service = ComplexDiscoveryService(db)
    discovery_result = run_async(service.discover_complexes(region_code))

    # Step 2: 해당 지역 활성 단지 조회
    region_prefix = region_code[:5] if len(region_code) >= 5 else region_code
    complexes = (
        db.query(Complex)
        .filter(
            Complex.region_code.like(f"{region_prefix}%"),
            Complex.is_active == True,
        )
        .all()
    )

    if not complexes:
        logger.warning(f"No active complexes found for region {region_code}")
        run.status = RunStatus.SUCCESS
        run.finished_at = now_kst()
        db.commit()
        return {
            "region_code": region_code,
            "discovery": discovery_result,
            "run_id": run.id,
            "total_tasks": 0,
        }

    # Step 3: 태스크 실행
    total_tasks = 0
    for complex_obj in complexes:
        # 단지 기본 정보 수집
        ensure_complex_detail(db, complex_obj)

        # 단지 주변 학군 수집 (이미 있으면 스킵)
        ensure_complex_facilities(db, complex_obj)

        # 면적이 없으면 KB API에서 자동 조회
        areas = complex_obj.areas or ensure_complex_areas(db, complex_obj)

        # 자식 collect_* 태스크는 다른 prefork worker가 즉시 픽업한다.
        # ensure_* 가 만든 row를 자식 트랜잭션에서 보려면 enqueue 전 commit 필수.
        db.commit()

        for area in areas:
            collect_kb_price_task.delay(
                run_id=run.id,
                complex_id=complex_obj.id,
                area_id=area.id,
            )
            total_tasks += 1

        # 매물 수집 (단지별)
        collect_kb_listing_task.delay(
            run_id=run.id,
            complex_id=complex_obj.id,
        )
        total_tasks += 1

    run.total_tasks = total_tasks
    db.commit()

    logger.info(
        f"Region collection for {region_code}: "
        f"{len(complexes)} complexes, {total_tasks} tasks launched"
    )
    return {
        "region_code": region_code,
        "discovery": discovery_result,
        "run_id": run.id,
        "total_tasks": total_tasks,
        "complexes_count": len(complexes),
    }


@celery_app.task(base=DatabaseTask, bind=True)
def run_scheduled_job(self, job_id: int) -> Dict[str, Any]:
    """celery beat 가 cron 시점에 호출 — CrawlJob 의 target 에 따라 단지들을 모아 수집 trigger.

    target_config 형식:
      {"sido_code": "11"}        — 시도 단위
      {"region_code": "11350"}   — 시군구 단위
      {"dong_code": "1135010500"} — 동 단위
    """
    from src.models.crawl import CrawlJob, JobStatus

    db = self.db
    job = db.query(CrawlJob).filter(CrawlJob.id == job_id).first()
    if not job or job.status != JobStatus.ACTIVE:
        logger.info(f"[scheduled_job] {job_id}: skipped (not active)")
        return {"status": "skipped"}

    try:
        cfg = json.loads(job.target_config) if job.target_config else {}
    except (json.JSONDecodeError, TypeError):
        cfg = {}

    q = db.query(Complex).filter(Complex.is_active.is_(True))
    if cfg.get("dong_code"):
        q = q.filter(Complex.dong_code == cfg["dong_code"])
    elif cfg.get("region_code"):
        q = q.filter(Complex.region_code == cfg["region_code"])
    elif cfg.get("sido_code"):
        q = q.filter(Complex.region_code.like(f"{cfg['sido_code']}%"))
    else:
        logger.warning(f"[scheduled_job] {job_id}: invalid target_config {cfg}")
        return {"status": "invalid"}

    complexes = q.all()
    if not complexes:
        logger.info(f"[scheduled_job] {job_id}: no complexes for {cfg}")
        return {"status": "no_complexes"}

    run = CrawlRun(job_id=job.id, status=RunStatus.PENDING, started_at=now_kst())
    db.add(run)
    db.commit()

    target_config = json.dumps({"complex_ids": [c.id for c in complexes]})
    run_kb_collection.delay(job_id=job.id, run_id=run.id, target_config=target_config)
    logger.info(f"[scheduled_job] {job_id}: triggered {len(complexes)} complexes (run={run.id})")
    return {"status": "triggered", "run_id": run.id, "count": len(complexes)}


# ─── 좀비 RUNNING task/run 자동 정리 ───────────────────────────────────────────
# Celery worker SIGSEGV/OOM 등으로 task 가 비정상 종료되면 DB 의 status 가
# RUNNING/PENDING 인 채로 남는다. 이게 누적되면 통계가 오염되고 finalize 가
# 안 끝난다. 5분마다 실행해서 일정 시간 이상 멈춰있는 task/run 을 FAILED 처리.

ZOMBIE_TASK_TIMEOUT_MIN = 10  # 10분 이상 RUNNING — 좀비
ZOMBIE_RUN_TIMEOUT_MIN = 60  # 60분 이상 RUNNING — 좀비 (대규모 수집 고려)


@celery_app.task
def cleanup_zombie_runs() -> Dict[str, Any]:
    """타임아웃을 넘긴 RUNNING task/run 을 FAILED 로 정리."""
    from datetime import timedelta

    db: Session = SessionLocal()
    try:
        now = now_kst()
        task_cutoff = now - timedelta(minutes=ZOMBIE_TASK_TIMEOUT_MIN)
        run_cutoff = now - timedelta(minutes=ZOMBIE_RUN_TIMEOUT_MIN)

        # 1) 좀비 task: started_at 이 task_cutoff 보다 오래된 RUNNING/PENDING
        zombie_tasks = (
            db.query(CrawlTask)
            .filter(
                CrawlTask.status.in_([TaskStatus.RUNNING, TaskStatus.PENDING]),
                CrawlTask.started_at.isnot(None),
                CrawlTask.started_at < task_cutoff,
            )
            .all()
        )
        # PENDING 인데 started_at 이 NULL 인 경우는 created_at 기준
        zombie_pending = (
            db.query(CrawlTask)
            .filter(
                CrawlTask.status == TaskStatus.PENDING,
                CrawlTask.started_at.is_(None),
                CrawlTask.created_at < task_cutoff,
            )
            .all()
        )
        for t in zombie_tasks + zombie_pending:
            t.status = TaskStatus.FAILED
            t.error_type = "ZombieTimeout"
            t.error_message = (
                f"task stuck in {t.status.value} > {ZOMBIE_TASK_TIMEOUT_MIN}min, "
                f"likely worker crash"
            )
            t.finished_at = now

        # 2) 좀비 run: started_at 이 run_cutoff 보다 오래된 RUNNING
        zombie_runs = (
            db.query(CrawlRun)
            .filter(
                CrawlRun.status.in_([RunStatus.RUNNING, RunStatus.PENDING]),
                CrawlRun.started_at.isnot(None),
                CrawlRun.started_at < run_cutoff,
            )
            .all()
        )
        for r in zombie_runs:
            r.status = RunStatus.FAILED
            r.finished_at = now
            r.error_summary = (
                f'{{"reason": "zombie_timeout", "stuck_for_min": ' f"{ZOMBIE_RUN_TIMEOUT_MIN}}}"
            )

        db.commit()
        result = {
            "tasks_cleaned": len(zombie_tasks) + len(zombie_pending),
            "runs_cleaned": len(zombie_runs),
        }
        if result["tasks_cleaned"] or result["runs_cleaned"]:
            logger.warning(f"[cleanup_zombie_runs] {result}")
        return result
    except Exception as e:
        db.rollback()
        logger.error(f"[cleanup_zombie_runs] failed: {e}")
        raise
    finally:
        db.close()


# =============================================================================
# 국토교통부 실거래가 (MOLIT) 수집
# =============================================================================


def _normalize_apt_name(s: str) -> str:
    """단지명 정규화 — 공백·괄호·구두점 제거, 소문자. fuzzy 매칭용."""
    import re

    if not s:
        return ""
    return re.sub(r"\s+|[()()【】\-\.,]", "", s).lower()


def _match_complex_id(db: Session, sgg_cd: str, umd_cd: str, apt_nm: str) -> Optional[int]:
    """MOLIT 거래의 (시군구코드, 법정동코드, 단지명) 으로 KB DB 의 complex 매칭."""
    apt_norm = _normalize_apt_name(apt_nm)
    if not apt_norm or not sgg_cd:
        return None

    dong_code = f"{sgg_cd}{umd_cd}" if umd_cd else None
    # dong_code 정확 매칭 후보 + dong_code NULL 인 같은 시군구 단지도 포함
    if dong_code:
        rows = (
            db.query(Complex.id, Complex.name)
            .filter(
                (Complex.dong_code == dong_code)
                | (Complex.dong_code.is_(None) & Complex.region_code.like(f"{sgg_cd}%"))
            )
            .all()
        )
    else:
        rows = (
            db.query(Complex.id, Complex.name).filter(Complex.region_code.like(f"{sgg_cd}%")).all()
        )
    # 정규화 정확 매칭 우선
    for cid, name in rows:
        if _normalize_apt_name(name) == apt_norm:
            return cid
    # contains fallback (한쪽이 다른쪽 포함)
    for cid, name in rows:
        n = _normalize_apt_name(name)
        if n and (apt_norm in n or n in apt_norm):
            return cid
    return None


@celery_app.task(base=DatabaseTask, bind=True)
def collect_molit_transaction_task(
    self,
    run_id: int,
    region_code: str,
    contract_month: str,
) -> Dict[str, Any]:
    """국토교통부 실거래가 수집 (시군구 LAWD_CD 5자리 × YYYYMM 1개월).

    KB DB 의 단지와 매칭된 거래만 transactions 에 UPSERT (KB 가 이미 가진 같은 거래는
    UNIQUE 인덱스로 skip). 매칭 못 한 거래는 통계로만 기록.
    """
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    from src.connectors.molit_transaction import MolitTransactionConnector
    from src.core.config import settings

    db = self.db
    task_key = f"molit_transaction_{region_code}_{contract_month}"
    task_record = CrawlTask(
        run_id=run_id,
        task_key=task_key,
        status=TaskStatus.RUNNING,
        started_at=now_kst(),
    )
    db.add(task_record)
    db.commit()

    try:
        conn = MolitTransactionConnector(rate_limit_per_minute=settings.molit_rate_limit_per_minute)
        result = conn.fetch(region_code=region_code, contract_month=contract_month)
        items = result["data"]
        parsed = conn.parse(items)

        matched = 0
        inserted = 0
        skipped_unmatched = 0
        for raw, p in zip(items, parsed, strict=False):
            cid = _match_complex_id(db, raw.get("sggCd", ""), raw.get("umdCd", ""), p["_apt_name"])
            if cid is None:
                skipped_unmatched += 1
                continue
            matched += 1
            stmt = (
                pg_insert(Transaction)
                .values(
                    complex_id=cid,
                    contract_date=p["contract_date"],
                    price=p["price"],
                    exclusive_m2=p["exclusive_m2"],
                    floor=p["floor"],
                    is_cancelled=p["is_cancelled"],
                    source="molit",
                    source_id=p.get("source_id"),
                    fetched_at=now_kst(),
                )
                .on_conflict_do_nothing(
                    index_elements=[
                        "complex_id",
                        "contract_date",
                        "price",
                        "exclusive_m2",
                        "floor",
                    ]
                )
            )
            res = db.execute(stmt)
            if res.rowcount and res.rowcount > 0:
                inserted += 1
        db.commit()

        task_record.status = TaskStatus.SUCCESS
        task_record.items_collected = len(parsed)
        task_record.items_saved = inserted
        logger.info(
            f"Task {task_key}: raw={len(parsed)} matched={matched} "
            f"inserted={inserted} unmatched={skipped_unmatched}"
        )
        return {
            "status": "success",
            "raw": len(parsed),
            "matched": matched,
            "inserted": inserted,
            "skipped_unmatched": skipped_unmatched,
        }
    except BaseException as e:
        logger.exception(f"Task {task_key} failed: {e}")
        try:
            db.rollback()
        except Exception:
            pass
        task_record.status = TaskStatus.FAILED
        task_record.error_type = type(e).__name__
        task_record.error_message = str(e)[:500]
        return {"status": "failed", "error": str(e)}
    finally:
        task_record.finished_at = now_kst()
        try:
            db.commit()
        except Exception:
            pass
        _finalize_run_if_complete(db, run_id)
