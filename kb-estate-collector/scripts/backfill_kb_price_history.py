"""KB 월별 시세 추이 백필.

KB land 의 PerMn/IntgrationChart 가 단지·면적당 N개월치 시세를 한 번에 반환.
호출당 한 (단지, 면적) → kb_prices 테이블에 월별 행을 UPSERT.

사용:
    python scripts/backfill_kb_price_history.py --months 36                      # 전체 단지 × 36개월
    python scripts/backfill_kb_price_history.py --prefix 11350 --months 36       # 노원구만
    python scripts/backfill_kb_price_history.py --start-from 11350 --months 36   # 노원구부터
    python scripts/backfill_kb_price_history.py --reset                          # state 초기화
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import date, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

import httpx
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

from sqlalchemy import create_engine
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import sessionmaker

from src.core.time import now_kst
from src.models.complex import Area, Complex
from src.models.price_data import KBPrice

STATE_FILE = Path(__file__).parent / "backfill_kb_price_history_state.json"
ENDPOINT = "https://api.kbland.kr/land-price/price/PerMn/IntgrationChart"
HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
    "AppleWebKit/537.36 Chrome/120.0 Safari/537.36",
    "Origin": "https://kbland.kr",
    "Referer": "https://kbland.kr/",
}


def load_state() -> set[str]:
    if STATE_FILE.exists():
        return set(json.loads(STATE_FILE.read_text()))
    return set()


def save_state(done: set[str]) -> None:
    STATE_FILE.write_text(json.dumps(sorted(done)))


def fetch_history(
    client: httpx.Client,
    kb_complex_id: str,
    kb_area_code: str,
    since_yyyymmdd: str,
    until_yyyymmdd: str,
) -> list[dict]:
    """IntgrationChart 호출 → flatten 된 월별 시세 dict 리스트."""
    params = {
        "단지기본일련번호": kb_complex_id,
        "면적일련번호": kb_area_code,
        "거래구분": 0,  # 전체
        "조회구분": 2,
        "조회시작일": since_yyyymmdd,
        "조회종료일": until_yyyymmdd,
    }
    r = client.get(ENDPOINT, params=params)
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:120]}")
    data = r.json().get("dataBody", {}).get("data", {})
    series = data.get("시세", [])
    out: list[dict] = []
    for grp in series:
        for it in grp.get("items", []):
            ym = it.get("기준년월")
            if not ym or len(ym) != 6:
                continue
            general = it.get("매매일반거래가")
            if not general:
                continue  # 매매 시세 없는 월은 skip
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


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--months", type=int, default=36, help="백필 개월 수 (기본 36)")
    ap.add_argument("--prefix", type=str, default=None, help="시도/시군구 prefix 필터")
    ap.add_argument("--start-from", type=str, default=None, help="region_code 시작점")
    ap.add_argument("--rate", type=float, default=2.1, help="호출 간 초 (30/min 안전)")
    ap.add_argument("--reset", action="store_true")
    args = ap.parse_args()

    if args.reset and STATE_FILE.exists():
        STATE_FILE.unlink()
        print("[backfill] state reset")

    today = date.today()
    since = (today - timedelta(days=args.months * 31)).strftime("%Y%m%d")
    until = today.strftime("%Y%m%d")
    print(f"[backfill] 기간: {since} ~ {until}")

    eng = create_engine(os.environ["DATABASE_URL"])
    Session = sessionmaker(bind=eng)
    db = Session()
    try:
        q = db.query(Complex.id, Complex.name, Complex.kb_complex_id, Complex.region_code).filter(
            Complex.kb_complex_id.isnot(None)
        )
        if args.prefix:
            q = q.filter(Complex.region_code.like(f"{args.prefix}%"))
        if args.start_from:
            q = q.filter(Complex.region_code >= args.start_from)
        q = q.order_by(Complex.region_code, Complex.id)
        complexes = q.all()
        print(f"[backfill] 대상 단지 {len(complexes)}개")

        done = load_state()
        processed = 0
        total_inserted = 0
        with httpx.Client(headers=HEADERS, timeout=20.0) as client:
            for c in complexes:
                areas = (
                    db.query(Area.id, Area.kb_area_code)
                    .filter(Area.complex_id == c.id, Area.kb_area_code.isnot(None))
                    .all()
                )
                for a in areas:
                    key = f"{c.id}_{a.id}"
                    if key in done:
                        continue
                    processed += 1
                    try:
                        rows = fetch_history(client, c.kb_complex_id, a.kb_area_code, since, until)
                        inserted = 0
                        for r in rows:
                            stmt = (
                                pg_insert(KBPrice)
                                .values(
                                    complex_id=c.id,
                                    area_id=a.id,
                                    as_of_date=r["as_of_date"],
                                    general_price=r["general_price"],
                                    high_avg_price=r["high_avg_price"],
                                    low_avg_price=r["low_avg_price"],
                                    source="kb_history",
                                    fetched_at=now_kst(),
                                )
                                .on_conflict_do_nothing(
                                    index_elements=["complex_id", "area_id", "as_of_date"]
                                )
                            )
                            res = db.execute(stmt)
                            if res.rowcount and res.rowcount > 0:
                                inserted += 1
                        db.commit()
                        total_inserted += inserted
                        done.add(key)
                        if processed % 20 == 0:
                            save_state(done)
                        if inserted > 0 or processed % 50 == 0:
                            print(
                                f"  [{len(done)}] {c.region_code} {c.name[:20]:20s} area#{a.id}: "
                                f"months={len(rows)} ins={inserted}"
                            )
                    except Exception as e:
                        print(f"  [{c.id}/{a.id}] ERROR {type(e).__name__}: {e}")
                    time.sleep(args.rate)
        save_state(done)
        print(f"\n[backfill] done. total_inserted={total_inserted}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
