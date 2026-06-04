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
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from src.connectors import KBListingConnector, KBPriceConnector, KBTransactionConnector
from src.core.config import settings
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
        # 트랜잭션 abort 상태로 두면 같은 세션을 쓰는 호출자(run_kb_collection)의
        # 다음 단지 처리에서 InFailedSqlTransaction 으로 연쇄 실패한다.
        try:
            db.rollback()
        except Exception:
            pass
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

    return db.query(Complex).filter(Complex.is_active.is_(True)).all()


def _run_cancelled(db: Session, run_id: int) -> bool:
    """run.status 가 RUNNING 이 아니면 True. revoke 안 된 broker 잔여 task 가
    시작될 때 즉시 종료하기 위한 가드.
    """
    run = db.query(CrawlRun).filter(CrawlRun.id == run_id).first()
    return run is None or run.status != RunStatus.RUNNING


def _begin_task(db: Session, run_id: int, task_key: str) -> CrawlTask:
    """task row 를 RUNNING 으로 시작. UNIQUE(run_id, task_key) 하에서 redeliver 시
    기존 row 를 재사용해 중복 INSERT(IntegrityError)·카운트 오염을 막는다(멱등)."""
    existing = db.query(CrawlTask).filter_by(run_id=run_id, task_key=task_key).first()
    if existing is not None:
        existing.status = TaskStatus.RUNNING
        existing.started_at = now_kst()
        db.commit()
        return existing
    task = CrawlTask(
        run_id=run_id, task_key=task_key, status=TaskStatus.RUNNING, started_at=now_kst()
    )
    db.add(task)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        task = db.query(CrawlTask).filter_by(run_id=run_id, task_key=task_key).first()
        task.status = TaskStatus.RUNNING
        task.started_at = now_kst()
        db.commit()
    return task


def _run_status_counts(db: Session, run_id: int) -> Dict[Any, int]:
    """run 의 태스크를 status 별로 집계 (GROUP BY COUNT). 전수 ORM 로딩 회피."""
    from sqlalchemy import func

    return dict(
        db.query(CrawlTask.status, func.count())
        .filter(CrawlTask.run_id == run_id)
        .group_by(CrawlTask.status)
        .all()
    )


def _apply_run_terminal(
    run: CrawlRun, counts: Dict[Any, int], *, reason: Optional[str] = None
) -> RunStatus:
    """집계 결과로 run 을 종료 상태(SUCCESS/PARTIAL/FAILED)로 전이. commit 은 호출자 책임."""
    success = counts.get(TaskStatus.SUCCESS, 0)
    failed = counts.get(TaskStatus.FAILED, 0)
    skipped = counts.get(TaskStatus.SKIPPED, 0)
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
    if reason:
        run.error_summary = reason
    return run.status


def _finalize_run_if_complete(db: Session, run_id: int):
    """leaf/prepare 완료 시 호출되는 fast-path 마감. 모든 태스크가 끝났으면 종료 전이.

    완주 보장의 단일 의존점이 되지 않도록 의도적으로 가볍게 유지한다 — 이 트리거를
    놓쳐도(worker recycle 등) cleanup_zombie_runs 의 drain-sweep 이 5분 내 집계만으로 마감.
    """
    run = db.query(CrawlRun).filter(CrawlRun.id == run_id).first()
    if not run or run.status != RunStatus.RUNNING:
        return

    total = run.total_tasks or 0
    if total == 0:
        return

    # prepare 단계가 끝나기 전엔 child 가 계속 enqueue 되어 total 이 증가 중 → 마감 금지.
    prepare_total = run.prepare_total or 0
    if prepare_total > 0 and (run.prepare_done_count or 0) < prepare_total:
        return

    counts = _run_status_counts(db, run_id)
    finished = (
        counts.get(TaskStatus.SUCCESS, 0)
        + counts.get(TaskStatus.FAILED, 0)
        + counts.get(TaskStatus.SKIPPED, 0)
    )
    if finished < total:
        return

    status = _apply_run_terminal(run, counts)
    db.commit()
    logger.info(
        f"Run {run_id} finalized: {status.value} "
        f"(success={run.success_count}, failed={run.failed_count}, skipped={run.skipped_count})"
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
    if _run_cancelled(db, run_id):
        return {"status": "skipped", "reason": "run cancelled"}
    task_key = f"kb_price_{complex_id}_{area_id}"

    task_record = _begin_task(db, run_id, task_key)

    try:
        connector = KBPriceConnector(
            db_session=db, rate_limit_per_minute=settings.kb_rate_limit_per_minute
        )
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
                # UPSERT — 동시 worker 가 같은 거래 INSERT 시 race 로 인한 UniqueViolation 회피.
                # idx_transaction_unique = (complex_id, contract_date, price, exclusive_m2, floor)
                from sqlalchemy.dialects.postgresql import insert as pg_insert

                stmt = (
                    pg_insert(Transaction)
                    .values(
                        complex_id=complex_id,
                        contract_date=tx_data["contract_date"],
                        price=tx_data["price"],
                        exclusive_m2=exclusive_m2,
                        floor=tx_data.get("floor"),
                        source="kb",
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
    if _run_cancelled(db, run_id):
        return {"status": "skipped", "reason": "run cancelled"}
    task_key = f"kb_transaction_{complex_id}_{area_id or 'all'}"

    task_record = _begin_task(db, run_id, task_key)

    try:
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        connector = KBTransactionConnector(
            db_session=db, rate_limit_per_minute=settings.kb_rate_limit_per_minute
        )
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
    if _run_cancelled(db, run_id):
        return {"status": "skipped", "reason": "run cancelled"}
    task_key = f"kb_listing_{complex_id}"

    task_record = _begin_task(db, run_id, task_key)

    try:
        connector = KBListingConnector(
            db_session=db, rate_limit_per_minute=settings.kb_rate_limit_per_minute
        )
        # 매매(1) + 전세(2) 각각 호출. KB 가 거래유형 필터를 응답에 적용 → trade_type 정확
        items_by_id: Dict[str, dict] = {}
        for trade_code in ("1", "2"):
            result = connector.collect(complex_id=complex_id, trade_code=trade_code)
            for item in result["items"]:
                items_by_id[item["source_listing_id"]] = item
        all_items = list(items_by_id.values())
        seen_ids = list(items_by_id.keys())

        # 단지의 현재 호가만 유지. source_listing_id UNIQUE → upsert.
        # 이번 응답에 없는 기존 ACTIVE 는 REMOVED 로 전이 (CLAUDE.md §5).
        from sqlalchemy import case
        from sqlalchemy.dialects.postgresql import insert as pg_insert

        batch_at = now_kst()
        saved_count = 0
        for item in all_items:
            stmt = pg_insert(Listing).values(
                complex_id=complex_id,
                source_listing_id=item["source_listing_id"],
                ask_price=item["ask_price"],
                exclusive_m2=item.get("exclusive_m2"),
                floor=item.get("floor"),
                trade_type=item.get("trade_type"),
                status=ListingStatus.ACTIVE,
                posted_at=item.get("posted_at"),
                source="kb",
                fetched_at=batch_at,
                last_seen_at=batch_at,
                status_updated_at=batch_at,
            )
            stmt = stmt.on_conflict_do_update(
                index_elements=["source_listing_id"],
                set_={
                    "complex_id": stmt.excluded.complex_id,
                    "ask_price": stmt.excluded.ask_price,
                    "exclusive_m2": stmt.excluded.exclusive_m2,
                    "floor": stmt.excluded.floor,
                    "trade_type": stmt.excluded.trade_type,
                    "status": ListingStatus.ACTIVE,
                    "posted_at": stmt.excluded.posted_at,
                    "fetched_at": batch_at,
                    "last_seen_at": batch_at,
                    # REMOVED 였다가 ACTIVE 복원될 때만 갱신. 계속 ACTIVE 면 그대로 유지.
                    "status_updated_at": case(
                        (Listing.status != ListingStatus.ACTIVE, batch_at),
                        else_=Listing.status_updated_at,
                    ),
                },
            )
            db.execute(stmt)
            saved_count += 1

        # seen_ids 에 없는 기존 ACTIVE 매물은 REMOVED.
        removed_q = db.query(Listing).filter(
            Listing.complex_id == complex_id,
            Listing.status == ListingStatus.ACTIVE,
        )
        if seen_ids:
            removed_q = removed_q.filter(~Listing.source_listing_id.in_(seen_ids))
        removed_count = removed_q.update(
            {"status": ListingStatus.REMOVED, "status_updated_at": batch_at},
            synchronize_session=False,
        )

        db.commit()
        task_record.status = TaskStatus.SUCCESS
        task_record.items_collected = len(all_items)
        task_record.items_saved = saved_count
        logger.info(f"Task {task_key} completed: {len(all_items)} items, {removed_count} removed")
        return {
            "status": "success",
            "items_collected": len(all_items),
            "removed": removed_count,
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


# =============================================================================
# 단지 prepare (ensure_* 를 worker pool 로 분리)
# =============================================================================


@celery_app.task(base=DatabaseTask, bind=True)
def prepare_complex_task(
    self,
    run_id: int,
    complex_id: int,
    enqueue_transaction: bool = True,
) -> Dict[str, Any]:
    """단지 prepare: detail/facilities/areas 채우고 자식 수집 task 들을 enqueue.

    master 가 단지마다 ensure_* 를 sync 로 부르면 KB Facility + OSM 4종 호출
    (학교/지하철/병원/공원) 로 단지당 2~12초 block 됨 → worker idle. 그래서
    prepare 단계 자체를 worker pool 로 분산.

    total_tasks 는 child enqueue 직전에 atomic 증가시키고 enqueue 후 자기를
    SUCCESS 로 마킹. _finalize_run_if_complete 가 잘못된 시점에 finalize 하는
    걸 피하려고 순서가 중요하다.
    """
    db = self.db
    if _run_cancelled(db, run_id):
        return {"status": "skipped", "reason": "run cancelled"}
    task_key = f"kb_prepare_{complex_id}"

    # 멱등 재진입: redeliver 로 이미 완료된 prepare 면 total/prepare_done 재증가 없이 종료.
    already_done = (
        db.query(CrawlTask)
        .filter(
            CrawlTask.run_id == run_id,
            CrawlTask.task_key == task_key,
            CrawlTask.status == TaskStatus.SUCCESS,
        )
        .first()
    )
    if already_done:
        return {"status": "skipped", "reason": "prepare already done"}

    task_record = _begin_task(db, run_id, task_key)

    try:
        complex_obj = db.query(Complex).filter(Complex.id == complex_id).first()
        if not complex_obj:
            raise ValueError(f"Complex {complex_id} not found")

        ensure_complex_detail(db, complex_obj)
        ensure_complex_facilities(db, complex_obj)
        areas = complex_obj.areas or ensure_complex_areas(db, complex_obj)
        db.commit()

        # 품질 가드: kb_complex_id 가 있는데 면적 0건이면 KB 조회 실패(일시적 장애 등) —
        # 빈 데이터로 prepare-SUCCESS 시키지 않고 실패로 가시화해 다음 run 에서 재시도되게 한다.
        if not areas and complex_obj.kb_complex_id:
            raise ValueError(f"complex {complex_id}: KB 면적 조회 0건 — 데이터 불완전, 재수집 필요")

        per_area = 2 if enqueue_transaction else 1
        new_count = len(areas) * per_area + 1  # +1 = listing

        # 1. child enqueue (areas 는 위에서 commit 됨 — 자식이 자기 세션에서 row 를 본다)
        for area in areas:
            collect_kb_price_task.delay(
                run_id=run_id,
                complex_id=complex_id,
                area_id=area.id,
            )
            if enqueue_transaction:
                collect_kb_transaction_task.delay(
                    run_id=run_id,
                    complex_id=complex_id,
                    area_id=area.id,
                )
        collect_kb_listing_task.delay(
            run_id=run_id,
            complex_id=complex_id,
        )

        # 2. prepare SUCCESS + total_tasks/prepare_done_count 를 한 트랜잭션에서 1회만 증가.
        #    증가를 SUCCESS commit 과 묶는다 — already_done 가드는 SUCCESS row 만 잡으므로,
        #    증가를 SUCCESS 이전에 두면 크래시 후 redeliver(acks_late) 재실행 시 보상 행 없이
        #    total 이 두 번 더해진다(phantom). child 가 먼저 끝나도 완료 게이트
        #    (prepare_done < prepare_total)가 헛 finalize 를 막으므로 증가가 늦어도 안전.
        task_record.status = TaskStatus.SUCCESS
        task_record.finished_at = now_kst()
        db.query(CrawlRun).filter(CrawlRun.id == run_id).update(
            {
                CrawlRun.total_tasks: CrawlRun.total_tasks + new_count,
                CrawlRun.prepare_done_count: CrawlRun.prepare_done_count + 1,
            }
        )
        db.commit()

        _finalize_run_if_complete(db, run_id)
        return {
            "status": "success",
            "areas": len(areas),
            "children_enqueued": new_count,
        }

    except Exception as e:
        logger.exception(f"prepare_complex_task failed for complex {complex_id}: {e}")
        try:
            db.rollback()
        except Exception:
            pass
        task_record.status = TaskStatus.FAILED
        task_record.error_type = type(e).__name__
        task_record.error_message = str(e)[:500]
        task_record.finished_at = now_kst()
        # 실패한 prepare 도 child 를 안 만들고 종결되므로 게이트상 '처리됨'으로 카운트.
        db.query(CrawlRun).filter(CrawlRun.id == run_id).update(
            {CrawlRun.prepare_done_count: CrawlRun.prepare_done_count + 1}
        )
        try:
            db.commit()
        except Exception:
            pass
        _finalize_run_if_complete(db, run_id)
        raise


# =============================================================================
# KB 통합 수집 (시세 + 최근실거래가)
# =============================================================================


@celery_app.task(base=DatabaseTask, bind=True, acks_late=False, reject_on_worker_lost=False)
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

        # prepare 단계를 worker pool 로 분산 — master 는 단지마다 prepare 만 enqueue.
        # prepare_complex_task 가 ensure_* 후 collect_* child 들을 직접 enqueue 하고
        # CrawlRun.total_tasks 를 atomic 증가시킨다.
        # total_tasks 는 prepare 가 child 를 더하는 단일출처 — redeliver 시 덮어쓰지 않는다.
        if not run.total_tasks:
            run.total_tasks = len(complexes)
        run.prepare_total = len(complexes)
        db.commit()

        for complex_obj in complexes:
            prepare_complex_task.delay(
                run_id=run.id,
                complex_id=complex_obj.id,
                enqueue_transaction=True,
            )

        logger.info(
            f"Run {run.id}: Launched {len(complexes)} prepare tasks "
            f"(child collect tasks will be enqueued by prepare)"
        )
        return {
            "run_id": run.id,
            "total_tasks": len(complexes),
            "complexes_count": len(complexes),
        }

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
def discover_active_regions(self) -> Dict[str, Any]:
    """활성 배치 잡의 대상 지역을 시군구 단위로 펼쳐 단지 발견을 일괄 디스패치.

    celery beat 가 주기 호출(주간). 신규 아파트를 자동 등록만 하고, 시세는 해당
    지역의 다음 정기 수집(run_scheduled_job)이 가져간다 — 가격 수집 경로와 분리.
    discover_complexes 는 시군구(5자리)/법정동(10자리)만 받으므로 시도(2자리) 잡은
    이미 적재된 단지의 region_code 로 시군구를 역산해 펼친다.
    """
    from sqlalchemy import func

    from src.models.crawl import CrawlJob, JobStatus

    db = self.db
    jobs = db.query(CrawlJob).filter(CrawlJob.status == JobStatus.ACTIVE).all()

    sigungu_codes: set = set()
    for job in jobs:
        try:
            cfg = json.loads(job.target_config) if job.target_config else {}
        except (json.JSONDecodeError, TypeError):
            continue
        if cfg.get("dong_code"):
            sigungu_codes.add(cfg["dong_code"])
        elif cfg.get("region_code"):
            sigungu_codes.add(cfg["region_code"])
        elif cfg.get("region_codes"):
            sigungu_codes.update(cfg["region_codes"])
        elif cfg.get("sido_code"):
            rows = (
                db.query(func.distinct(func.substr(Complex.region_code, 1, 5)))
                .filter(
                    Complex.region_code.like(f"{cfg['sido_code']}%"),
                    Complex.is_active.is_(True),
                    Complex.region_code.isnot(None),
                )
                .all()
            )
            sigungu_codes.update(r[0] for r in rows if r[0])

    for code in sorted(sigungu_codes):
        discover_complexes_task.delay(code)

    logger.info(
        f"[discover_active_regions] dispatched discovery for {len(sigungu_codes)} sigungu "
        f"from {len(jobs)} active jobs"
    )
    return {"dispatched": len(sigungu_codes), "sigungu": sorted(sigungu_codes)}


@celery_app.task(base=DatabaseTask, bind=True, acks_late=False, reject_on_worker_lost=False)
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
            Complex.is_active.is_(True),
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

    # Step 3: prepare 단계를 worker pool 로 분산 (run_kb_collection 과 동일 패턴).
    # region 수집은 transaction 미포함이라 flag 로 분기.
    if not run.total_tasks:
        run.total_tasks = len(complexes)
    run.prepare_total = len(complexes)
    db.commit()

    for complex_obj in complexes:
        prepare_complex_task.delay(
            run_id=run.id,
            complex_id=complex_obj.id,
            enqueue_transaction=False,
        )

    logger.info(f"Region collection for {region_code}: " f"{len(complexes)} prepare tasks launched")
    return {
        "region_code": region_code,
        "discovery": discovery_result,
        "run_id": run.id,
        "total_tasks": len(complexes),
        "complexes_count": len(complexes),
    }


@celery_app.task(base=DatabaseTask, bind=True, acks_late=False, reject_on_worker_lost=False)
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
    elif cfg.get("region_codes"):
        # 시군구 묶음 타겟 — 대형 시도(서울/경기)를 하루치 청크로 쪼갠 배치용
        q = q.filter(Complex.region_code.in_(cfg["region_codes"]))
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

    # 같은 region 의 KB 시세 history 백필도 동시에 trigger.
    # backfill 은 IntgrationChart API 직접 호출이라 정기 수집과 worker concurrency 만 공유.
    backfill_prefix = cfg.get("dong_code") or cfg.get("region_code") or cfg.get("sido_code")
    if backfill_prefix:
        backfill_kb_price_history_task.delay(region_prefix=backfill_prefix)

    logger.info(f"[scheduled_job] {job_id}: triggered {len(complexes)} complexes (run={run.id})")
    return {"status": "triggered", "run_id": run.id, "count": len(complexes)}


# ─── 좀비 RUNNING task/run 자동 정리 ───────────────────────────────────────────
# Celery worker SIGSEGV/OOM 등으로 task 가 비정상 종료되면 DB 의 status 가
# RUNNING/PENDING 인 채로 남는다. 5분마다 실행해서 정리한다.
# run 은 절대 수명으로 판정하지 않는다 — 시도 단위 대규모 수집은 10시간 넘게
# 정상 진행될 수 있다. 마지막 task 가 집어진 지 IDLE_MIN 넘도록 새 활동이
# 없을 때만 worker 가 죽은 것으로 보고 좀비 처리한다.

ZOMBIE_TASK_TIMEOUT_MIN = 60  # task 가 60분 넘게 RUNNING — worker crash 로 간주
ZOMBIE_RUN_IDLE_MIN = 60  # run 의 마지막 task 활동 후 60분 정체 — 좀비
DRAIN_GRACE_MIN = 3  # 큐 0 + RUNNING/PENDING task 0 이 이만큼 유지되면 drain 완료로 정식 마감
WORKER_LIVENESS_MIN = (
    10  # 이 시간 내 전역 task 활동이 있으면 worker 생존 — 큐 대기 중인 run 은 좀비 보류
)


_COLLECTION_QUEUES = ("dispatch", "prepare", "fast", "slow")


def _broker_queue_depth() -> int:
    """수집 큐(dispatch/prepare/fast/slow) 미처리 메시지 합. 읽기 실패 시 -1 (drain 판정 보류).

    run 의 모든 child 가 이 큐들에 분산되므로 drain 판정은 네 큐를 모두 합산해야 한다.
    """
    try:
        import redis

        client = redis.from_url(settings.celery_broker_url)
        try:
            return sum(int(client.llen(q)) for q in _COLLECTION_QUEUES)
        finally:
            client.close()
    except Exception as e:
        logger.warning(f"[cleanup] broker queue depth read failed: {e}")
        return -1


@celery_app.task
def cleanup_zombie_runs() -> Dict[str, Any]:
    """타임아웃을 넘긴 RUNNING task, task 활동이 멈춘 run 을 FAILED 로 정리."""
    from datetime import timedelta

    from sqlalchemy import func

    db: Session = SessionLocal()
    try:
        now = now_kst()
        task_cutoff = now - timedelta(minutes=ZOMBIE_TASK_TIMEOUT_MIN)
        run_idle_cutoff = now - timedelta(minutes=ZOMBIE_RUN_IDLE_MIN)

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

        # 1.5) drain-sweep: 완주 보장의 핵심 안전망.
        #   큐가 비고(queue_depth==0) RUNNING/PENDING task 가 0 이며 마지막 활동이 grace 를
        #   넘긴 run 은 완전히 빠진(drain) 것 → total_tasks 정확성과 무관하게 실제 집계로
        #   정식 마감(SUCCESS/PARTIAL/FAILED). leaf push 트리거(_finalize)가 worker recycle
        #   등으로 유실돼도 5분 내 유한시간 종결을 보장한다.
        swept = 0
        queue_depth = _broker_queue_depth()
        if queue_depth == 0:
            drain_grace_cutoff = now - timedelta(minutes=DRAIN_GRACE_MIN)
            running_runs = (
                db.query(CrawlRun)
                .filter(
                    CrawlRun.status == RunStatus.RUNNING,
                    CrawlRun.started_at.isnot(None),
                )
                .all()
            )
            for r in running_runs:
                counts = _run_status_counts(db, r.id)
                if counts.get(TaskStatus.RUNNING, 0) + counts.get(TaskStatus.PENDING, 0) > 0:
                    continue  # 아직 처리 중인 task 가 있으면 drain 아님
                last_act = (
                    db.query(func.max(func.coalesce(CrawlTask.started_at, CrawlTask.created_at)))
                    .filter(CrawlTask.run_id == r.id)
                    .scalar()
                ) or r.started_at
                if last_act >= drain_grace_cutoff:
                    continue  # 방금 빈 것일 수 있음 — grace 동안 대기
                prep_total = r.prepare_total or 0
                prep_done = r.prepare_done_count or 0
                finished = (
                    counts.get(TaskStatus.SUCCESS, 0)
                    + counts.get(TaskStatus.FAILED, 0)
                    + counts.get(TaskStatus.SKIPPED, 0)
                )
                total = r.total_tasks or 0
                prepares_incomplete = prep_total > 0 and prep_done < prep_total
                # prepare 는 다 됐는데 child 가 total 에 못 미치면 = child 메시지 유실/미실행.
                # prepare_done 만 보고 SUCCESS 로 위장하지 않도록 child 기준도 본다.
                children_incomplete = total > 0 and finished < total
                incomplete = prepares_incomplete or children_incomplete
                reason = None
                if prepares_incomplete:
                    # 큐가 빈 채 prepare 미완 = prepare 메시지 유실 → 데이터 불완전.
                    reason = (
                        '{"reason": "drained_incomplete_prepares", '
                        f'"prepare_done": {prep_done}, "prepare_total": {prep_total}}}'
                    )
                elif children_incomplete:
                    reason = (
                        '{"reason": "drained_incomplete_children", '
                        f'"finished": {finished}, "total_tasks": {total}}}'
                    )
                _apply_run_terminal(r, counts, reason=reason)
                if incomplete:
                    # 불완전 수집을 SUCCESS 로 위장하지 않는다.
                    r.status = RunStatus.PARTIAL if r.success_count > 0 else RunStatus.FAILED
                swept += 1

        # drain-sweep 가 방금 마감한 run(PARTIAL/SUCCESS/FAILED)을 아래 zombie 쿼리가
        # 다시 집어 zombie_idle/FAILED 로 덮어쓰지 않도록 flush — autoflush=False 라
        # flush 없이는 status IN(RUNNING,PENDING) 필터가 미반영 상태(DB값)로 평가되고
        # identity-map 이 같은 인스턴스를 반환해 drained_incomplete_* 마킹이 유실된다.
        db.flush()

        # 2) 좀비 run: 마지막 task 활동(started_at)이 idle_cutoff 보다 오래됐으면
        #    worker 가 죽은 것. run 이 실제로 task 를 처리 중이면 살려둔다.
        last_act = (
            db.query(
                CrawlTask.run_id.label("run_id"),
                func.max(func.coalesce(CrawlTask.started_at, CrawlTask.created_at)).label("act"),
            )
            .group_by(CrawlTask.run_id)
            .subquery()
        )
        zombie_runs = (
            db.query(CrawlRun)
            .outerjoin(last_act, last_act.c.run_id == CrawlRun.id)
            .filter(
                CrawlRun.status.in_([RunStatus.RUNNING, RunStatus.PENDING]),
                CrawlRun.started_at.isnot(None),
                func.coalesce(last_act.c.act, CrawlRun.started_at) < run_idle_cutoff,
            )
            .all()
        )

        # worker 가 살아서 공유 큐를 비우는 중이면, 대형 run 이 fast/slow 큐를 선점한 동안
        # 소형 run 의 child 가 아직 broker 에서 대기 중인 것 — idle 처럼 보여도 좀비가 아니다.
        # queue_depth != 0 (메시지 잔존, 또는 -1=broker 읽기 실패) + 최근 전역 task 활동이면
        # child 도착 전이므로 죽이지 않고 기다린다. queue_depth==0 이면 위 drain-sweep 이
        # 정식 마감하므로 가드 불필요 — 이때 workers_alive 풀스캔도 단락으로 생략한다.
        # 읽기 실패(-1) 는 마감 보류 쪽(fail-safe)으로 둬 broker 일시 장애에 데이터를 지킨다.
        system_draining = queue_depth != 0 and (
            db.query(CrawlTask.id)
            .filter(
                func.coalesce(CrawlTask.finished_at, CrawlTask.started_at)
                >= now - timedelta(minutes=WORKER_LIVENESS_MIN),
                # cleanup 이 방금/직전에 마킹한 좀비 task(finished_at=now)를 'worker 활동'으로
                # 오인하지 않도록 제외 — 안 그러면 진짜 worker 사망 사이클에 system_draining
                # 위양성이 되어 좀비 run 마감이 최대 WORKER_LIVENESS_MIN 만큼 지연된다.
                CrawlTask.error_type.is_distinct_from("ZombieTimeout"),
            )
            .first()
            is not None
        )

        killed = 0
        guarded = 0
        for r in zombie_runs:
            # 좀비로 마감하되 그 시점까지의 task 결과를 카운트에 반영 (0/0/0 오염 방지)
            counts = dict(
                db.query(CrawlTask.status, func.count())
                .filter(CrawlTask.run_id == r.id)
                .group_by(CrawlTask.status)
                .all()
            )
            success = counts.get(TaskStatus.SUCCESS, 0)
            failed = counts.get(TaskStatus.FAILED, 0)
            skipped = counts.get(TaskStatus.SKIPPED, 0)
            finished = success + failed + skipped
            # 큐가 비워지는 중이고 아직 처리 못한 promised child 가 남았으면 child 가 broker 에
            # 대기 중 — 죽이지 말고 기다린다(데이터 손실 방지). worker 가 진짜 죽었으면
            # system_draining=False 라 이 가드가 안 걸려 정상적으로 좀비 마감된다.
            if system_draining and (r.total_tasks or 0) > finished:
                guarded += 1
                continue
            r.success_count = success
            r.failed_count = failed
            r.skipped_count = skipped
            r.status = RunStatus.FAILED
            r.finished_at = now
            r.error_summary = f'{{"reason": "zombie_idle", "idle_min": {ZOMBIE_RUN_IDLE_MIN}}}'
            killed += 1

        db.commit()
        result = {
            "tasks_cleaned": len(zombie_tasks) + len(zombie_pending),
            "runs_cleaned": killed,
            "runs_guarded": guarded,
            "runs_finalized": swept,
        }
        if any(result.values()):
            logger.warning(f"[cleanup_zombie_runs] {result}")
        return result
    except Exception as e:
        db.rollback()
        logger.error(f"[cleanup_zombie_runs] failed: {e}")
        raise
    finally:
        db.close()


# =============================================================================
# KB 시세 월별 history 백필
# =============================================================================

_KB_HISTORY_ENDPOINT = "https://api.kbland.kr/land-price/price/PerMn/IntgrationChart"
_KB_HISTORY_HEADERS = {
    "User-Agent": (
        "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
        "AppleWebKit/537.36 Chrome/120.0 Safari/537.36"
    ),
    "Origin": "https://kbland.kr",
    "Referer": "https://kbland.kr/",
}


def _fetch_kb_price_history(
    client,
    kb_complex_id: str,
    kb_area_code: str,
    since_yyyymmdd: str,
    until_yyyymmdd: str,
) -> List[Dict[str, Any]]:
    """KB IntgrationChart → 월별 시세 dict 리스트. 매매가 없는 월은 skip."""
    params = {
        "단지기본일련번호": kb_complex_id,
        "면적일련번호": kb_area_code,
        "거래구분": 0,
        "조회구분": 2,
        "조회시작일": since_yyyymmdd,
        "조회종료일": until_yyyymmdd,
    }
    r = client.get(_KB_HISTORY_ENDPOINT, params=params)
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:120]}")
    data = r.json().get("dataBody", {}).get("data") or {}
    out: List[Dict[str, Any]] = []
    # KB 는 데이터 없으면 "시세": null 로 반환하기도 함 → or [] 로 정규화
    for grp in data.get("시세") or []:
        for it in grp.get("items") or []:
            ym = it.get("기준년월")
            if not ym or len(ym) != 6:
                continue
            general = it.get("매매일반거래가")
            if not general:
                continue
            out.append(
                {
                    "as_of_date": f"{ym[:4]}-{ym[4:6]}-01",
                    "general_price": int(general) * 10000,
                    "high_avg_price": int(it["매매상한가"]) * 10000
                    if it.get("매매상한가")
                    else None,
                    "low_avg_price": int(it["매매하한가"]) * 10000
                    if it.get("매매하한가")
                    else None,
                }
            )
    return out


@celery_app.task(bind=True)
def backfill_kb_price_history_task(
    self,
    months: int = 36,
    batch_limit: int = 5000,
    max_runtime_sec: int = 1800,
    rate_sec: float = 1.1,
    region_prefix: Optional[str] = None,
) -> Dict[str, Any]:
    """KB 월별 시세 백필 — (단지,면적) 미수집 페어를 시간/배치 한도까지 처리.

    region_prefix 가 주어지면 해당 region_code prefix 단지만 대상.
    정기 수집 task 가 시도별 cron 시점에 region_prefix=sido_code 로 trigger.
    """
    import time
    from datetime import date, timedelta

    import httpx
    from sqlalchemy import text
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    db: Session = SessionLocal()
    started = time.monotonic()
    today = date.today()
    since = (today - timedelta(days=months * 31)).strftime("%Y%m%d")
    until = today.strftime("%Y%m%d")

    processed = 0
    inserted_total = 0
    errors = 0
    try:
        pairs = db.execute(
            text(
                """
                SELECT c.id AS complex_id, c.kb_complex_id,
                       a.id AS area_id, a.kb_area_code
                FROM complexes c
                JOIN areas a ON a.complex_id = c.id
                LEFT JOIN (
                    SELECT DISTINCT complex_id, area_id
                    FROM kb_prices
                    WHERE source LIKE 'kb_history%'
                ) p ON p.complex_id = c.id AND p.area_id = a.id
                WHERE c.kb_complex_id IS NOT NULL
                  AND a.kb_area_code IS NOT NULL
                  AND p.complex_id IS NULL
                  AND (:prefix IS NULL OR c.region_code LIKE :prefix_like)
                ORDER BY c.region_code, c.id, a.id
                LIMIT :lim
                """
            ),
            {
                "lim": batch_limit,
                "prefix": region_prefix,
                "prefix_like": f"{region_prefix}%" if region_prefix else None,
            },
        ).fetchall()

        if not pairs:
            logger.info("[backfill_kb_price_history] 미백필 페어 없음")
            return {"processed": 0, "inserted": 0, "errors": 0, "remaining": 0}

        with httpx.Client(headers=_KB_HISTORY_HEADERS, timeout=20.0) as client:
            for row in pairs:
                if time.monotonic() - started > max_runtime_sec:
                    break
                try:
                    items = _fetch_kb_price_history(
                        client,
                        row.kb_complex_id,
                        row.kb_area_code,
                        since,
                        until,
                    )
                    if not items:
                        # KB 에 36개월 history 없음 → sentinel 1행으로 done 표시
                        db.execute(
                            pg_insert(KBPrice)
                            .values(
                                complex_id=row.complex_id,
                                area_id=row.area_id,
                                as_of_date=date(1900, 1, 1),
                                general_price=None,
                                high_avg_price=None,
                                low_avg_price=None,
                                source="kb_history_empty",
                                fetched_at=now_kst(),
                            )
                            .on_conflict_do_nothing(
                                index_elements=["complex_id", "area_id", "as_of_date"]
                            )
                        )
                    for it in items:
                        stmt = (
                            pg_insert(KBPrice)
                            .values(
                                complex_id=row.complex_id,
                                area_id=row.area_id,
                                as_of_date=it["as_of_date"],
                                general_price=it["general_price"],
                                high_avg_price=it["high_avg_price"],
                                low_avg_price=it["low_avg_price"],
                                source="kb_history",
                                fetched_at=now_kst(),
                            )
                            .on_conflict_do_nothing(
                                index_elements=["complex_id", "area_id", "as_of_date"]
                            )
                        )
                        res = db.execute(stmt)
                        if res.rowcount and res.rowcount > 0:
                            inserted_total += 1
                    db.commit()
                    processed += 1
                except Exception as e:
                    db.rollback()
                    errors += 1
                    logger.warning(
                        f"[backfill_kb_price_history] complex#{row.complex_id} "
                        f"area#{row.area_id}: {type(e).__name__}: {e}"
                    )
                time.sleep(rate_sec)

        remaining = db.execute(
            text(
                """
                SELECT COUNT(*) FROM areas a
                JOIN complexes c ON c.id = a.complex_id
                LEFT JOIN (
                    SELECT DISTINCT complex_id, area_id
                    FROM kb_prices WHERE source LIKE 'kb_history%'
                ) p ON p.complex_id = c.id AND p.area_id = a.id
                WHERE c.kb_complex_id IS NOT NULL
                  AND a.kb_area_code IS NOT NULL
                  AND p.complex_id IS NULL
                  AND (:prefix IS NULL OR c.region_code LIKE :prefix_like)
                """
            ),
            {
                "prefix": region_prefix,
                "prefix_like": f"{region_prefix}%" if region_prefix else None,
            },
        ).scalar()

        result = {
            "processed": processed,
            "inserted": inserted_total,
            "errors": errors,
            "remaining": int(remaining or 0),
            "elapsed_sec": int(time.monotonic() - started),
            "region_prefix": region_prefix,
        }
        logger.info(f"[backfill_kb_price_history] {result}")
        return result
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
    task_record = _begin_task(db, run_id, task_key)

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
