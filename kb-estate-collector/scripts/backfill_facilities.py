"""기존 단지에 facility(학군/지하철/병원) 백필.

facility 가 없는 단지 + kb_complex_id 가 있는 단지에 대해 KB API 호출.
지하철/병원은 Complex.lat/lng 가 채워져 있어야 수집 (없으면 학군만).

usage:
    python scripts/backfill_facilities.py --region 11350
    python scripts/backfill_facilities.py --limit 10
"""
from __future__ import annotations

import argparse
import asyncio
import sys
from collections import Counter
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import select

from src.core.database import SessionLocal
from src.core.time import now_kst
from src.connectors.kb_facility import KBFacilityConnector
from src.models import Complex, ComplexFacility


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--region", type=str, default=None, help="시군구코드 5자리")
    parser.add_argument("--rate", type=int, default=30, help="분당 호출 한도")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        # 좌표 기반 facility(subway/hospital/park) 가 없는 단지가 대상.
        # 학군만 있던 옛 잔재 단지도 보강. 학군은 삭제 후 재수집되어 cutoff 재적용.
        coord_complexes = (
            select(ComplexFacility.complex_id)
            .where(ComplexFacility.facility_type.in_(["subway", "hospital", "park"]))
            .distinct()
            .scalar_subquery()
        )
        q = (
            db.query(Complex)
            .filter(Complex.kb_complex_id.isnot(None))
            .filter(~Complex.id.in_(coord_complexes))
        )
        if args.region:
            q = q.filter(Complex.region_code == args.region)
        if args.limit:
            q = q.limit(args.limit)
        targets = q.all()
        total = len(targets)
        print(f"[backfill_facilities] target: {total} complexes")

        if not total:
            print("nothing to backfill.")
            return

        from src.workers.tasks import SCHOOL_DISTANCE_CUTOFF

        connector = KBFacilityConnector(rate_limit_per_minute=args.rate)
        ok = fail = saved_total = 0
        for i, c in enumerate(targets, 1):
            try:
                # 학군만 잔존하면 삭제 후 재수집 (cutoff 재적용 + 통합 수집)
                db.query(ComplexFacility).filter(
                    ComplexFacility.complex_id == c.id
                ).delete(synchronize_session=False)
                db.commit()  # delete 즉시 반영 — 이후 INSERT가 UNIQUE 충돌 안 나도록

                items = await connector.fetch_all(c.kb_complex_id, lat=c.lat, lng=c.lng)
                # 응답 내 중복 제거 (facility_type, external_id) 기준 — KB가 학교 5단계 호출 시
                # 같은 학교가 다른 등급으로 두 번 반환되는 등의 케이스 방지
                seen = set()
                deduped = []
                for it in items:
                    key = (it["facility_type"], it.get("external_id"))
                    if key[1] and key in seen:
                        continue
                    seen.add(key)
                    deduped.append(it)
                items = deduped
                count = 0
                now = now_kst()
                for item in items:
                    if item["facility_type"] == "school":
                        cutoff = SCHOOL_DISTANCE_CUTOFF.get(item.get("sub_type") or "")
                        if cutoff and item.get("distance_m") is not None and item["distance_m"] > cutoff:
                            continue
                    fac = ComplexFacility(
                        complex_id=c.id,
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
                    db.add(fac)
                    count += 1
                db.commit()  # 단지별 commit — 한 건 실패해도 다른 단지 영향 X
                saved_total += count
                ok += 1
                cat = Counter(it["facility_type"] for it in items)
                if i % 5 == 0 or i <= 5:
                    print(f"  [{i}/{total}] {c.name}: {dict(cat)}")
            except Exception as e:
                db.rollback()
                fail += 1
                print(f"  [error] {c.name}: {str(e)[:150]}")
            await asyncio.sleep(60.0 / args.rate)

        db.commit()
        print(f"\n[backfill_facilities] done. ok={ok}, fail={fail}, saved={saved_total}")
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
