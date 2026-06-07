"""배치(crawl_jobs) 주간 스케줄 디코딩 — read-only.

crawl_jobs.cron_schedule(단일 출처)을 요일·시각·실측소요·겹침·커버리지로 풀어
JSON 으로 반환한다. Admin API(`GET /api/batches/schedule`)와 CLI 스크립트
(`scripts/show_batch_schedule.py`)가 공유하는 단일 로직.
"""
from __future__ import annotations

import json

from sqlalchemy import text
from sqlalchemy.orm import Session

# 직렬 처리 1단지당 추정 소요(러프). 실측 run 이력이 없는 잡에만 폴백으로 사용.
SEC_PER_COMPLEX = 8.0

DOW_NAME = {0: "일", 1: "월", 2: "화", 3: "수", 4: "목", 5: "금", 6: "토"}
DOW_ORDER = {1: 0, 2: 1, 3: 2, 4: 3, 5: 4, 6: 5, 0: 6}  # 월요일 시작 정렬
ORDER_DOW = {v: k for k, v in DOW_ORDER.items()}

# 주소에서 시군구명 역산 (region_code 가 권위 키, 이름은 가독성 라벨일 뿐)
_SIGUNGU_EXPR = """
    CASE
        WHEN split_part(address,' ',3) LIKE '%구' AND split_part(address,' ',2) LIKE '%시'
            THEN split_part(address,' ',2)||' '||split_part(address,' ',3)
        ELSE split_part(address,' ',2)
    END
"""


def _parse_cron(cron):
    """'min hour dom mon dow' → (minute, hour, dow). 파싱 불가면 None."""
    if not cron:
        return None
    parts = cron.split()
    if len(parts) != 5:
        return None
    m, h, _dom, _mon, dow = parts
    if any(x == "*" for x in (m, h, dow)):
        return None
    try:
        return int(m), int(h), int(dow)
    except ValueError:
        return None


def _start_mow(minute, hour, dow):
    """주간 분(월요일=0 기준)."""
    return DOW_ORDER.get(dow, 0) * 1440 + hour * 60 + minute


def _add_hours(minute, hour, dow, dur_hours):
    """시작에 dur_hours 더한 종료 (end_dow[cron], end_h, end_m). 주 단위 wrap."""
    mow = round(_start_mow(minute, hour, dow) + dur_hours * 60) % (7 * 1440)
    order, rem = mow // 1440, mow % 1440
    return ORDER_DOW[order], rem // 60, rem % 60


def _load_last_runs(db: Session):
    """job_id → {'hours', 'status'} (최근 완료 SUCCESS/PARTIAL run 실측)."""
    rows = db.execute(
        text(
            "SELECT DISTINCT ON (job_id) job_id, status, "
            "EXTRACT(EPOCH FROM (finished_at - started_at))/3600.0 AS hours "
            "FROM crawl_runs "
            "WHERE finished_at IS NOT NULL AND started_at IS NOT NULL "
            "AND status IN ('SUCCESS','PARTIAL') "
            "ORDER BY job_id, started_at DESC"
        )
    ).all()
    return {r.job_id: {"hours": float(r.hours), "status": r.status} for r in rows}


def _load_region_map(db: Session):
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
            f"  SELECT region_code, {_SIGUNGU_EXPR} AS name, count(*) AS cnt "
            "  FROM complexes WHERE length(region_code)=5 GROUP BY 1, 2"
            ") t ORDER BY region_code, cnt DESC"
        )
    ).all()
    for r in names:
        if r.region_code in rmap:
            rmap[r.region_code]["name"] = (r.name or "").strip() or "(미상)"
    return rmap


def _job_target(cfg: dict, rmap: dict):
    """target_config → (kind, region_code 리스트, 요약문자열)."""
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
        return "sido", [c for c in rmap if c.startswith(sido)], f"시도 {sido} 전체"
    return "unknown", [], json.dumps(cfg, ensure_ascii=False)


def build_schedule(db: Session) -> dict:
    """주간 스케줄 디코딩 결과(JSON 직렬화 가능 dict)."""
    rmap = _load_region_map(db)
    last_runs = _load_last_runs(db)
    jobs = db.execute(
        text("SELECT id, name, status, cron_schedule, target_config FROM crawl_jobs ORDER BY id")
    ).all()

    active, paused = [], []
    for j in jobs:
        cfg = json.loads(j.target_config) if j.target_config else {}
        kind, codes, summary = _job_target(cfg, rmap)
        n = sum(rmap.get(c, {}).get("total", 0) for c in codes)
        lr = last_runs.get(j.id)
        dur = lr["hours"] if lr else n * SEC_PER_COMPLEX / 3600.0
        dur_src = f"실측({lr['status'][:4]})" if lr else "추정"
        rec = {
            "job_id": j.id,
            "name": j.name,
            "cron": j.cron_schedule,
            "kind": kind,
            "codes": codes,
            "summary": summary,
            "complexes": n,
            "dur_hours": round(dur, 2),
            "dur_source": dur_src,
        }
        (active if j.status == "ACTIVE" else paused).append(rec)

    # 주간 스케줄 (cron 걸린 active 만, 월요일 시작 시간순)
    timed = [(r, _parse_cron(r["cron"])) for r in active]
    timed = [(r, pc) for r, pc in timed if pc]
    timed.sort(key=lambda x: _start_mow(x[1][0], x[1][1], x[1][2]))

    schedule = []
    for r, (m, h, dow) in timed:
        end_dow, end_h, end_m = _add_hours(m, h, dow, r["dur_hours"])
        schedule.append(
            {
                "job_id": r["job_id"],
                "name": r["name"],
                "dow": dow,
                "hour": h,
                "minute": m,
                "dow_name": DOW_NAME.get(dow, "?"),
                "kind": r["kind"],
                "summary": r["summary"],
                "complexes": r["complexes"],
                "dur_hours": r["dur_hours"],
                "dur_source": r["dur_source"],
                "end_dow_name": DOW_NAME.get(end_dow, "?"),
                "end_hour": end_h,
                "end_minute": end_m,
                "crosses_day": DOW_ORDER.get(end_dow, 0) != DOW_ORDER.get(dow, 0),
            }
        )

    # 겹침 점검 (소요 기준 다음 잡 시작과 충돌)
    seq = sorted(
        [(_start_mow(m, h, dow), r) for r, (m, h, dow) in timed],
        key=lambda x: x[0],
    )
    clashes = []
    for i, (s, r) in enumerate(seq):
        ns, nr = seq[(i + 1) % len(seq)]
        if i == len(seq) - 1:
            ns += 7 * 1440  # 마지막 → 다음주 첫 잡 wrap
        if s + r["dur_hours"] * 60 > ns:
            clashes.append(
                {
                    "job_id": r["job_id"],
                    "name": r["name"],
                    "dur_hours": r["dur_hours"],
                    "next_job_id": nr["job_id"],
                    "next_name": nr["name"],
                    "overlap_hours": round((s + r["dur_hours"] * 60 - ns) / 60.0, 1),
                }
            )

    # 거대지역 청크 상세
    chunk_recs = [r for r in active if r["kind"] == "codes"]
    chunks = []
    for r in sorted(chunk_recs, key=lambda x: x["name"]):
        pc = _parse_cron(r["cron"])
        chunks.append(
            {
                "job_id": r["job_id"],
                "name": r["name"],
                "dow_name": DOW_NAME.get(pc[2], "?") if pc else None,
                "hour": pc[1] if pc else None,
                "minute": pc[0] if pc else None,
                "complexes": r["complexes"],
                "dur_hours": r["dur_hours"],
                "dur_source": r["dur_source"],
                "codes": [
                    {
                        "region_code": c,
                        "name": rmap.get(c, {}).get("name", "(DB에 없음)"),
                        "complexes": rmap.get(c, {}).get("total", 0),
                    }
                    for c in r["codes"]
                ],
            }
        )

    # 커버리지 검증 (시도별: 청크 union == DB 실제 코드?)
    by_sido: dict[str, list] = {}
    for r in chunk_recs:
        for c in r["codes"]:
            by_sido.setdefault(c[:2], []).append((r, c))
    coverage = []
    for sido in sorted(by_sido):
        assigned = [c for _, c in by_sido[sido]]
        chunk_set = set(assigned)
        db_set = {c for c in rmap if c.startswith(sido)}
        overlaps = sorted({c for c in assigned if assigned.count(c) > 1})
        missing = sorted(db_set - chunk_set)
        empty = sorted(chunk_set - db_set)
        coverage.append(
            {
                "sido": sido,
                "sido_name": by_sido[sido][0][0]["name"].split()[0],
                "chunk_codes": len(chunk_set),
                "db_codes": len(db_set),
                "ok": not (overlaps or missing or empty),
                "overlaps": overlaps,
                "missing": missing,
                "empty": empty,
            }
        )

    return {
        "schedule": schedule,
        "clashes": clashes,
        "chunks": chunks,
        "coverage": coverage,
        "paused": [
            {
                "job_id": r["job_id"],
                "name": r["name"],
                "summary": r["summary"],
                "complexes": r["complexes"],
            }
            for r in paused
        ],
    }
