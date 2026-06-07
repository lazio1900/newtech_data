"""배치(crawl_jobs) 스케줄·거대지역 청크 구성 확인용 read-only 인스펙션.

프론트 sido 배치 UI 는 region_codes 청크 잡을 안 보여주므로, 서울/경기 분할이
실제 DB(crawl_jobs)에 어떻게 들어가 있는지 직접 확인하는 용도다.

usage (도커 운영 모드):
    docker compose exec admin-api python scripts/show_batch_schedule.py
또는:
    docker exec kb-estate-collector-admin-api-1 python scripts/show_batch_schedule.py
"""
from __future__ import annotations

import json
import sys
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from sqlalchemy import text  # noqa: E402

from src.core.database import SessionLocal  # noqa: E402

# 직렬 처리 1단지당 추정 소요(러프). 실제는 매물 밀도에 따라 다름(서울≈7s·경기≈10s/단지).
SEC_PER_COMPLEX = 8.0

DOW_NAME = {0: "일", 1: "월", 2: "화", 3: "수", 4: "목", 5: "금", 6: "토"}
DOW_ORDER = {1: 0, 2: 1, 3: 2, 4: 3, 5: 4, 6: 5, 0: 6}  # 월요일 시작 정렬

# 주소에서 시군구명 역산 (region_code 가 권위 키, 이름은 가독성 라벨일 뿐)
SIGUNGU_EXPR = """
    CASE
        WHEN split_part(address,' ',3) LIKE '%구' AND split_part(address,' ',2) LIKE '%시'
            THEN split_part(address,' ',2)||' '||split_part(address,' ',3)
        ELSE split_part(address,' ',2)
    END
"""


def parse_cron(cron: str | None):
    """'min hour dom mon dow' → (minute, hour, dow). 필드가 '*' 면 None."""
    if not cron:
        return None
    parts = cron.split()
    if len(parts) != 5:
        return None
    m, h, _dom, _mon, dow = parts

    def num(x):
        return None if x == "*" else int(x)

    return num(m), num(h), num(dow)


def load_last_runs(db):
    """job_id → {'hours', 'status', 'when'} (최근 완료 SUCCESS/PARTIAL run 실측)."""
    rows = db.execute(
        text(
            "SELECT DISTINCT ON (job_id) job_id, status, started_at, "
            "EXTRACT(EPOCH FROM (finished_at - started_at))/3600.0 AS hours "
            "FROM crawl_runs "
            "WHERE finished_at IS NOT NULL AND started_at IS NOT NULL "
            "AND status IN ('SUCCESS','PARTIAL') "
            "ORDER BY job_id, started_at DESC"
        )
    ).all()
    return {
        r.job_id: {"hours": float(r.hours), "status": r.status, "when": r.started_at} for r in rows
    }


def load_region_map(db):
    """region_code(5자리) → {'total', 'active', 'name'}."""
    rows = db.execute(
        text(
            "SELECT region_code, count(*) AS total, "
            "count(*) FILTER (WHERE is_active) AS active "
            "FROM complexes WHERE length(region_code)=5 GROUP BY region_code"
        )
    ).all()
    rmap = {r.region_code: {"total": r.total, "active": r.active, "name": ""} for r in rows}

    names = db.execute(
        text(
            "SELECT DISTINCT ON (region_code) region_code, name FROM ("
            f"  SELECT region_code, {SIGUNGU_EXPR} AS name, count(*) AS cnt "
            "  FROM complexes WHERE length(region_code)=5 GROUP BY 1, 2"
            ") t ORDER BY region_code, cnt DESC"
        )
    ).all()
    for r in names:
        if r.region_code in rmap:
            rmap[r.region_code]["name"] = (r.name or "").strip() or "(미상)"
    return rmap


def job_target(cfg: dict, rmap: dict):
    """target_config → (종류, 대상 region_code 리스트, 요약문자열)."""
    if cfg.get("region_codes"):
        codes = list(cfg["region_codes"])
        return "codes", codes, f"{len(codes)}개 시군구"
    if cfg.get("region_code"):
        c = cfg["region_code"]
        return "code", [c], f"시군구 {c}"
    if cfg.get("dong_code"):
        return "dong", [], f"동 {cfg['dong_code']}"
    if cfg.get("sido_code"):
        sido = cfg["sido_code"]
        codes = [c for c in rmap if c.startswith(sido)]
        return "sido", codes, f"시도 {sido} 전체"
    return "?", [], json.dumps(cfg, ensure_ascii=False)


def total_complexes(codes, rmap):
    return sum(rmap.get(c, {}).get("total", 0) for c in codes)


def hours(n):
    return n * SEC_PER_COMPLEX / 3600.0


ORDER_DOW = {v: k for k, v in DOW_ORDER.items()}  # 월요일 시작 순번 → cron dow


def start_mow(pc):
    """(minute, hour, dow) → 주간 분(월요일=0 기준)."""
    m, h, dow = pc
    return DOW_ORDER.get(dow, 0) * 1440 + h * 60 + m


def add_hours(dow, h, m, dur_hours):
    """시작(dow,h,m)에 dur_hours 더한 종료 (end_dow[cron], end_h, end_m). 주 단위 wrap."""
    mow = (round(start_mow((m, h, dow)) + dur_hours * 60)) % (7 * 1440)
    order, rem = mow // 1440, mow % 1440
    return ORDER_DOW[order], rem // 60, rem % 60


def main():
    db = SessionLocal()
    try:
        rmap = load_region_map(db)
        last_runs = load_last_runs(db)
        jobs = db.execute(
            text(
                "SELECT id, name, status, cron_schedule, target_config "
                "FROM crawl_jobs ORDER BY id"
            )
        ).all()

        active, paused = [], []
        for j in jobs:
            cfg = json.loads(j.target_config) if j.target_config else {}
            kind, codes, summary = job_target(cfg, rmap)
            n = total_complexes(codes, rmap)
            lr = last_runs.get(j.id)
            if lr:
                dur, dur_src = lr["hours"], f"실측({lr['status'][:4]})"
            else:
                dur, dur_src = hours(n), "추정"
            rec = {
                "id": j.id,
                "name": j.name,
                "cron": j.cron_schedule,
                "kind": kind,
                "codes": codes,
                "summary": summary,
                "n": n,
                "dur": dur,
                "dur_src": dur_src,
            }
            (active if j.status == "ACTIVE" else paused).append(rec)

        # 1) 주간 스케줄
        print("=" * 78)
        print(" 주간 배치 스케줄 (ACTIVE)")
        print("=" * 78)
        sched = []
        for r in active:
            pc = parse_cron(r["cron"])
            sched.append((pc, r))
        sched.sort(
            key=lambda x: (
                DOW_ORDER.get(x[0][2], 9) if x[0] else 9,
                x[0][1] if x[0] else 99,
                x[0][0] if x[0] else 99,
            )
        )
        print(f"  {'요일 시각':<11} {'잡':<16} {'대상':<13} {'단지':>6} {'소요':>6}  종료")
        print("  " + "-" * 74)
        for pc, r in sched:
            if pc:
                m, h, dow = pc
                when = f"{DOW_NAME.get(dow, '?')} {h:02d}:{m:02d}"
                end_dow, end_h, end_m = add_hours(dow, h, m, r["dur"])
                cross = "+1d " if (DOW_ORDER.get(end_dow, 0) != DOW_ORDER.get(dow, 0)) else ""
                end = f"{DOW_NAME.get(end_dow, '?')} {end_h:02d}:{end_m:02d}{'' if not cross else ' (+1d)'}"
            else:
                when, end = f"(cron?:{r['cron']})", "-"
            print(
                f"  {when:<11} #{r['id']:<3}{r['name']:<15} {r['summary']:<13} "
                f"{r['n']:>6,} {r['dur']:>5.1f}h  {end}  [{r['dur_src']}]"
            )

        # 1b) 겹침 점검 (실측/추정 소요 기준 다음 잡과 시간 충돌?)
        timed = [(start_mow(pc), pc, r) for pc, r in sched if pc]
        timed.sort(key=lambda x: x[0])
        clashes = []
        for i, (s, _pc, r) in enumerate(timed):
            ns, _npc, nr = timed[(i + 1) % len(timed)]
            if i == len(timed) - 1:
                ns += 7 * 1440  # 마지막→다음주 첫 잡 wrap
            end = s + r["dur"] * 60
            if end > ns:
                clashes.append((r, nr, (end - ns) / 60.0))
        print("\n  --- 겹침 점검 (소요 기준 다음 잡 시작과 충돌) ---")
        if not clashes:
            print("    겹침 없음 ✓")
        for r, nr, ov in clashes:
            print(
                f"    ✗ #{r['id']} {r['name']}({r['dur']:.1f}h) → "
                f"#{nr['id']} {nr['name']} 시작과 ~{ov:.1f}h 겹침"
            )

        # 2) 거대지역 청크 상세
        print("\n" + "=" * 78)
        print(" 거대지역 청크 상세 (region_codes 분할 잡)")
        print("=" * 78)
        chunk_jobs = [r for r in active if r["kind"] == "codes"]
        for r in sorted(chunk_jobs, key=lambda x: x["name"]):
            pc = parse_cron(r["cron"])
            when = f"{DOW_NAME.get(pc[2], '?')} {pc[1]:02d}:{pc[0]:02d}" if pc else r["cron"]
            print(
                f"\n  ▸ #{r['id']} {r['name']}  [{when}]  {r['n']:,}단지  "
                f"{r['dur']:.1f}h [{r['dur_src']}]"
            )
            for c in r["codes"]:
                info = rmap.get(c, {"name": "(DB에 없음)", "total": 0})
                print(f"      {c}  {info['name']:<14} {info['total']:>5,}단지")

        # 3) 커버리지 검증 (청크 union vs DB 실제 코드)
        print("\n" + "=" * 78)
        print(" 커버리지 검증 (시도별: 청크 union == DB 실제 코드?)")
        print("=" * 78)
        by_sido = defaultdict(list)  # sido2 → [(job, code)]
        for r in chunk_jobs:
            for c in r["codes"]:
                by_sido[c[:2]].append((r, c))
        for sido in sorted(by_sido):
            assigned = [c for _, c in by_sido[sido]]
            chunk_set = set(assigned)
            overlaps = sorted({c for c in assigned if assigned.count(c) > 1})
            db_set = {c for c in rmap if c.startswith(sido)}
            missing = sorted(db_set - chunk_set)  # DB 에 있는데 어느 청크에도 없음
            empty = sorted(chunk_set - db_set)  # 청크에 있는데 DB 단지 0
            ok = not (overlaps or missing or empty)
            mark = "OK ✓" if ok else "문제 ✗"
            print(f"\n  시도 {sido}: 청크코드 {len(chunk_set)} / DB코드 {len(db_set)}  → {mark}")
            if overlaps:
                print(f"      중복(>1청크): {overlaps}")
            if missing:
                print(f"      누락(미수집): {missing}")
            if empty:
                print(f"      빈코드(단지0): {empty}")

        # 4) PAUSED (청크로 대체된 monolith 등)
        print("\n" + "=" * 78)
        print(" PAUSED 잡 (참고)")
        print("=" * 78)
        for r in paused:
            print(f"  #{r['id']:<3} {r['name']:<18} {r['summary']:<16} {r['n']:>6,}단지")
    finally:
        db.close()


if __name__ == "__main__":
    main()
