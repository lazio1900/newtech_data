"""배치(crawl_jobs) 주간 스케줄·청크 구성 확인용 read-only CLI.

디코딩 로직은 src.services.batch_schedule.build_schedule 단일 출처를 공유하고,
이 스크립트는 그 결과를 터미널 표로 출력만 한다. (UI 는 GET /api/batches/schedule)

usage:
    docker exec -i kb-estate-collector-admin-api-1 python - < scripts/show_batch_schedule.py
    # 또는 호스트 venv 모드: python scripts/show_batch_schedule.py
"""
from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.core.database import SessionLocal  # noqa: E402
from src.services.batch_schedule import build_schedule  # noqa: E402


def main():
    db = SessionLocal()
    try:
        data = build_schedule(db)
    finally:
        db.close()

    print("=" * 78)
    print(" 주간 배치 스케줄 (ACTIVE, 실측 소요 기반)")
    print("=" * 78)
    print(f"  {'요일 시각':<11} {'잡':<16} {'대상':<13} {'단지':>6} {'소요':>6}  종료")
    print("  " + "-" * 74)
    for s in data["schedule"]:
        when = f"{s['dow_name']} {s['hour']:02d}:{s['minute']:02d}"
        end = f"{s['end_dow_name']} {s['end_hour']:02d}:{s['end_minute']:02d}"
        if s["crosses_day"]:
            end += " (+1d)"
        print(
            f"  {when:<11} #{s['job_id']:<3}{s['name']:<15} {s['summary']:<13} "
            f"{s['complexes']:>6,} {s['dur_hours']:>5.1f}h  {end}  [{s['dur_source']}]"
        )

    print("\n  --- 겹침 점검 (소요 기준 다음 잡 시작과 충돌) ---")
    if not data["clashes"]:
        print("    겹침 없음 ✓")
    for c in data["clashes"]:
        print(
            f"    ✗ #{c['job_id']} {c['name']}({c['dur_hours']:.1f}h) → "
            f"#{c['next_job_id']} {c['next_name']} 시작과 ~{c['overlap_hours']:.1f}h 겹침"
        )

    print("\n" + "=" * 78)
    print(" 거대지역 청크 상세 (region_codes 분할 잡)")
    print("=" * 78)
    for ck in data["chunks"]:
        when = f"{ck['dow_name']} {ck['hour']:02d}:{ck['minute']:02d}"
        print(
            f"\n  ▸ #{ck['job_id']} {ck['name']}  [{when}]  {ck['complexes']:,}단지  "
            f"{ck['dur_hours']:.1f}h [{ck['dur_source']}]"
        )
        for c in ck["codes"]:
            print(f"      {c['region_code']}  {c['name']:<14} {c['complexes']:>5,}단지")

    print("\n" + "=" * 78)
    print(" 커버리지 검증 (시도별: 청크 union == DB 실제 코드?)")
    print("=" * 78)
    for cov in data["coverage"]:
        mark = "OK ✓" if cov["ok"] else "문제 ✗"
        print(
            f"\n  {cov['sido_name']}({cov['sido']}): 청크코드 {cov['chunk_codes']} / "
            f"DB코드 {cov['db_codes']}  → {mark}"
        )
        if cov["overlaps"]:
            print(f"      중복(>1청크): {cov['overlaps']}")
        if cov["missing"]:
            print(f"      누락(미수집): {cov['missing']}")
        if cov["empty"]:
            print(f"      빈코드(단지0): {cov['empty']}")

    print("\n" + "=" * 78)
    print(" PAUSED 잡 (참고)")
    print("=" * 78)
    for p in data["paused"]:
        print(f"  #{p['job_id']:<3} {p['name']:<18} {p['summary']:<16} {p['complexes']:>6,}단지")


if __name__ == "__main__":
    main()
