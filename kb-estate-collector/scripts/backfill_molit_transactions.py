"""국토교통부 실거래가 백필.

전국 시군구 × 최근 N개월. KB 가 누락한 거래를 보완 (UPSERT, KB 우선).
state 파일로 resume 지원 — 일일 quota(1000건) 초과로 중단 후 다음 날 재실행 가능.

사용:
    python scripts/backfill_molit_transactions.py --months 12
    python scripts/backfill_molit_transactions.py --months 6 --sgg 11680,11410
    python scripts/backfill_molit_transactions.py --reset     # state 초기화
"""

from __future__ import annotations

import argparse
import json
import os
import sys
import time
from datetime import date
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")

from sqlalchemy import create_engine, text
from sqlalchemy.dialects.postgresql import insert as pg_insert
from sqlalchemy.orm import sessionmaker

from src.connectors.base import NetworkError
from src.connectors.molit_transaction import MolitTransactionConnector
from src.core.time import now_kst
from src.models.price_data import Transaction
from src.workers.tasks import _match_complex_id

STATE_FILE = Path(__file__).parent / "backfill_molit_state.json"


def list_months(n: int) -> list[str]:
    """오늘로부터 직전월 ~ N개월 전. YYYYMM."""
    today = date.today()
    cur = date(today.year, today.month, 1)
    # 한 달 전으로 시작 (당월은 신뢰성 위해 제외)
    if cur.month == 1:
        cur = date(cur.year - 1, 12, 1)
    else:
        cur = date(cur.year, cur.month - 1, 1)
    out = []
    for _ in range(n):
        out.append(cur.strftime("%Y%m"))
        if cur.month == 1:
            cur = date(cur.year - 1, 12, 1)
        else:
            cur = date(cur.year, cur.month - 1, 1)
    return sorted(out)


def load_state() -> set[str]:
    if STATE_FILE.exists():
        return set(json.loads(STATE_FILE.read_text()))
    return set()


def save_state(done: set[str]) -> None:
    STATE_FILE.write_text(json.dumps(sorted(done)))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--months", type=int, default=12)
    ap.add_argument("--sgg", type=str, default=None, help="콤마구분 LAWD_CD. 기본 DB 전체")
    ap.add_argument(
        "--start-from",
        type=str,
        default=None,
        help="시작 시도/시군구 prefix. 예: '41' (경기부터), '41135' (성남 분당부터). 알파벳 순.",
    )
    ap.add_argument(
        "--prefix",
        type=str,
        default=None,
        help="시도/시군구 prefix 필터. 예: '11' (서울만), '41' (경기만).",
    )
    ap.add_argument("--rate", type=float, default=1.2, help="호출 간 초")
    ap.add_argument("--reset", action="store_true", help="state 초기화 후 진행")
    args = ap.parse_args()

    if args.reset and STATE_FILE.exists():
        STATE_FILE.unlink()
        print("[backfill] state reset")

    eng = create_engine(os.environ["DATABASE_URL"])
    Session = sessionmaker(bind=eng)
    db = Session()
    try:
        if args.sgg:
            sggs = [s.strip() for s in args.sgg.split(",") if s.strip()]
        else:
            rows = db.execute(
                text(
                    "SELECT DISTINCT SUBSTRING(region_code,1,5) FROM complexes "
                    "WHERE region_code IS NOT NULL AND LENGTH(region_code) >= 5 "
                    "ORDER BY 1"
                )
            ).fetchall()
            sggs = [r[0] for r in rows if r[0]]

        # prefix 필터 (예: '41' → 경기만)
        if args.prefix:
            sggs = [s for s in sggs if s.startswith(args.prefix)]
        # start-from (이 시점부터 알파벳 순 진행)
        if args.start_from:
            sggs = [s for s in sggs if s >= args.start_from]

        months = list_months(args.months)
        total = len(sggs) * len(months)
        print(
            f"[backfill] sgg={len(sggs)}, months={len(months)} ({months[0]}~{months[-1]}), tasks={total}"
        )

        done = load_state()
        print(f"[backfill] resume: {len(done)}/{total} already done")

        conn = MolitTransactionConnector()
        t_inserted = t_matched = t_unmatched = 0
        processed = 0
        for sgg in sggs:
            for month in months:
                key = f"{sgg}_{month}"
                if key in done:
                    continue
                processed += 1
                try:
                    result = conn.fetch(region_code=sgg, contract_month=month)
                    items = result["data"]
                    parsed = conn.parse(items)
                    matched = inserted = unmatched = 0
                    for raw, p in zip(items, parsed, strict=False):
                        cid = _match_complex_id(
                            db,
                            raw.get("sggCd", ""),
                            raw.get("umdCd", ""),
                            p["_apt_name"],
                        )
                        if not cid:
                            unmatched += 1
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
                        r = db.execute(stmt)
                        if r.rowcount and r.rowcount > 0:
                            inserted += 1
                    db.commit()
                    t_inserted += inserted
                    t_matched += matched
                    t_unmatched += unmatched
                    done.add(key)
                    if processed % 10 == 0 or inserted > 0:
                        save_state(done)
                    print(
                        f"  [{len(done)}/{total}] {key}: raw={len(parsed)} "
                        f"matched={matched} ins={inserted} unmatched={unmatched}"
                    )
                except NetworkError as e:
                    msg = str(e)
                    print(f"  [{key}] NETWORK ERROR: {msg[:120]}")
                    # 일일 quota 초과 등 인증 실패 → 그날은 정지
                    if "401" in msg or "Unauthorized" in msg or "LIMITED_NUMBER" in msg:
                        print(
                            "[backfill] daily quota or auth failure — stop. "
                            "내일 같은 명령 재실행하면 이어서 진행."
                        )
                        save_state(done)
                        return
                except Exception as e:
                    print(f"  [{key}] ERROR {type(e).__name__}: {e}")
                time.sleep(args.rate)
        save_state(done)
        print(
            f"\n[backfill] done. inserted={t_inserted} matched={t_matched} unmatched={t_unmatched}"
        )
    finally:
        db.close()


if __name__ == "__main__":
    main()
