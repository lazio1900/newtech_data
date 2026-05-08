"""기존 단지에 dong_code/dong_name 백필.

dong_code 가 비어 있는 단지 중 kb_complex_id 가 있는 것에 대해
KB API COMPLEX_DETAIL 호출해 채움. rate limit 고려.

usage:
    python scripts/backfill_dong_code.py            # 전체
    python scripts/backfill_dong_code.py --limit 10 # 10개만
    python scripts/backfill_dong_code.py --region 11350  # 노원구만
"""
from __future__ import annotations

import argparse
import asyncio
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.connectors.kb_endpoints import COMPLEX_DETAIL
from src.core.database import SessionLocal
from src.models.complex import Complex
from src.services.complex_discovery import _DiscoveryConnector


async def fetch_detail(connector, kb_complex_id: str) -> dict:
    """COMPLEX_DETAIL 응답에서 dong_code/dong_name/lat/lng 추출."""
    try:
        data = await connector._fetch_via_http(
            COMPLEX_DETAIL,
            {"단지기본일련번호": kb_complex_id, "물건종류": "01"},
        )
        body = data.get("dataBody", {}).get("data", {})
        out = {
            "dong_code": body.get("법정동코드") or body.get("dongCd"),
            "dong_name": body.get("읍면동명") or body.get("법정동명") or body.get("dongNm"),
            "lat": body.get("wgs84위도") or body.get("위도"),
            "lng": body.get("wgs84경도") or body.get("경도"),
        }
        return out
    except Exception as e:
        print(f"  [error] kb_complex_id={kb_complex_id}: {e}")
        return {}


async def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--region", type=str, default=None, help="시군구코드 5자리")
    parser.add_argument("--rate", type=int, default=30, help="분당 호출 한도")
    args = parser.parse_args()

    db = SessionLocal()
    try:
        from sqlalchemy import or_
        q = db.query(Complex).filter(
            Complex.kb_complex_id.isnot(None),
            or_(Complex.dong_code.is_(None), Complex.lat.is_(None)),
        )
        if args.region:
            q = q.filter(Complex.region_code == args.region)
        if args.limit:
            q = q.limit(args.limit)
        targets = q.all()
        total = len(targets)
        print(f"[backfill] target: {total} complexes")

        if not total:
            print("nothing to backfill.")
            return

        connector = _DiscoveryConnector(name="backfill", rate_limit_per_minute=args.rate)
        ok = fail = 0
        for i, c in enumerate(targets, 1):
            d = await fetch_detail(connector, c.kb_complex_id)
            if d.get("dong_code") or d.get("lat"):
                if d.get("dong_code"):
                    c.dong_code = str(d["dong_code"])
                if d.get("dong_name"):
                    c.dong_name = d["dong_name"]
                if d.get("lat"):
                    try: c.lat = float(d["lat"])
                    except (ValueError, TypeError): pass
                if d.get("lng"):
                    try: c.lng = float(d["lng"])
                    except (ValueError, TypeError): pass
                ok += 1
                if i % 10 == 0 or i <= 5:
                    print(f"  [{i}/{total}] {c.name} → dong={d.get('dong_code')} ({d.get('lat')},{d.get('lng')})")
                if i % 20 == 0:
                    db.commit()
            else:
                fail += 1
            # rate limit 보조 (커넥터 자체에도 제한 있지만 안전 마진)
            await asyncio.sleep(60.0 / args.rate)

        db.commit()
        print(f"\n[backfill] done. ok={ok}, fail={fail}, total={total}")
    finally:
        db.close()


if __name__ == "__main__":
    asyncio.run(main())
