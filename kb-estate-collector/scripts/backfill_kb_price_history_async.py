"""KB 월별 시세 추이 백필 — asyncio 동시성 버전.

기존 sync 버전(backfill_kb_price_history.py)과 같은 state 파일 공유.
httpx.AsyncClient + asyncio.Semaphore(N) 으로 동시 호출. 각 worker 가 호출 후
rate 초 sleep — 평균 throughput = 동시성 × (60 / (응답 + rate)) per minute.

사용:
    python scripts/backfill_kb_price_history_async.py --prefix 11 --months 36 --concurrency 5 --rate 1.0
    python scripts/backfill_kb_price_history_async.py --prefix 11 --concurrency 10 --rate 1.0
"""

from __future__ import annotations

import argparse
import asyncio
import json
import os
import sys
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


async def fetch_history(
    client: httpx.AsyncClient,
    kb_complex_id: str,
    kb_area_code: str,
    since: str,
    until: str,
) -> list[dict]:
    params = {
        "단지기본일련번호": kb_complex_id,
        "면적일련번호": kb_area_code,
        "거래구분": 0,
        "조회구분": 2,
        "조회시작일": since,
        "조회종료일": until,
    }
    r = await client.get(ENDPOINT, params=params)
    if r.status_code != 200:
        raise RuntimeError(f"HTTP {r.status_code}: {r.text[:120]}")
    data = r.json().get("dataBody", {}).get("data", {}) or {}
    series = data.get("시세") or []
    out: list[dict] = []
    for grp in series:
        for it in grp.get("items", []) or []:
            ym = it.get("기준년월")
            general = it.get("매매일반거래가")
            if not ym or len(ym) != 6 or not general:
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


async def main_async(args, pairs, since, until, db):
    sem = asyncio.Semaphore(args.concurrency)
    done = load_state()
    rate = args.rate
    total = len(pairs)
    counters = {"processed": 0, "inserted": 0, "fail": 0, "block": 0}

    async def worker(complex_id, kb_complex_id, area_id, kb_area_code, region_code, name):
        key = f"{complex_id}_{area_id}"
        if key in done:
            return
        async with sem:
            try:
                async with httpx.AsyncClient(headers=HEADERS, timeout=20.0) as client:
                    rows = await fetch_history(client, kb_complex_id, kb_area_code, since, until)
                # DB INSERT (sync session, main loop)
                ins = 0
                for r in rows:
                    stmt = (
                        pg_insert(KBPrice)
                        .values(
                            complex_id=complex_id,
                            area_id=area_id,
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
                        ins += 1
                db.commit()
                counters["inserted"] += ins
                done.add(key)
                counters["processed"] += 1
                if counters["processed"] % 25 == 0:
                    save_state(done)
                if ins > 0 or counters["processed"] % 50 == 0:
                    print(
                        f"  [{len(done)}/{total + len(done) - counters['processed']}] "
                        f"{region_code} {name[:20]:20s} area#{area_id} months={len(rows)} ins={ins}"
                    )
            except Exception as e:
                counters["fail"] += 1
                msg = str(e)
                if (
                    "401" in msg
                    or "Unauthorized" in msg
                    or "RemoteProtocolError" in type(e).__name__
                ):
                    counters["block"] += 1
                print(f"  ERR {complex_id}/{area_id}: {type(e).__name__}: {msg[:120]}")
            await asyncio.sleep(rate)

    tasks = [asyncio.create_task(worker(*p)) for p in pairs]
    await asyncio.gather(*tasks, return_exceptions=True)
    save_state(done)
    print(
        f"\n[backfill] done. inserted={counters['inserted']} fail={counters['fail']} block_signals={counters['block']}"
    )


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--months", type=int, default=36)
    ap.add_argument("--prefix", type=str, default=None)
    ap.add_argument("--start-from", type=str, default=None)
    ap.add_argument("--concurrency", type=int, default=5)
    ap.add_argument("--rate", type=float, default=1.0)
    args = ap.parse_args()

    today = date.today()
    since = (today - timedelta(days=args.months * 31)).strftime("%Y%m%d")
    until = today.strftime("%Y%m%d")
    print(f"[backfill] 기간: {since} ~ {until}, concurrency={args.concurrency}, rate={args.rate}s")

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

        pairs = []
        for c in complexes:
            areas = (
                db.query(Area.id, Area.kb_area_code)
                .filter(Area.complex_id == c.id, Area.kb_area_code.isnot(None))
                .all()
            )
            for a in areas:
                pairs.append((c.id, c.kb_complex_id, a.id, a.kb_area_code, c.region_code, c.name))
        print(f"[backfill] 대상 (단지·면적) {len(pairs):,}쌍")

        asyncio.run(main_async(args, pairs, since, until, db))
    finally:
        db.close()


if __name__ == "__main__":
    main()
