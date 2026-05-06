"""KB API COMPLEX_DETAIL 응답 키 확인용 일회성 probe.

usage:
    python scripts/probe_complex_detail.py 971
"""
from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.connectors.kb_endpoints import COMPLEX_DETAIL
from src.services.complex_discovery import _DiscoveryConnector


async def main(complex_no: str):
    connector = _DiscoveryConnector(name="probe", rate_limit_per_minute=30)
    data = await connector._fetch_via_http(
        COMPLEX_DETAIL,
        {"단지기본일련번호": complex_no, "물건종류": "01"},
    )
    body = data.get("dataBody", {}).get("data", {})

    print(f"=== complex_no={complex_no}, body fields={len(body)}개 ===\n")

    # 동/법정/주소/코드 관련 키만
    print("--- 동/법정/주소/현관/타입 관련 키 ---")
    for key, val in body.items():
        if any(x in key for x in ["동", "법정", "주소", "코드", "지역", "현관", "타입", "구조", "면적", "평"]):
            v = repr(val)
            if len(v) > 100:
                v = v[:100] + "..."
            print(f"  {key}: {v}")

    # 추측 키 직접 확인
    print("\n--- 추측 키 값 ---")
    for key in [
        "법정동코드", "법정동명", "법정동코드10자리", "법정동코드10",
        "dongCd", "dongNm", "동코드", "동이름",
        "신주소", "구주소", "도로기본주소", "지번주소",
        "시군구코드", "시군구명",
    ]:
        if key in body:
            print(f"  ✓ {key}: {body[key]!r}")
        else:
            print(f"  ✗ {key}: (없음)")

    # 전체 응답 일부
    print("\n--- 전체 응답 (처음 1500자) ---")
    print(json.dumps(body, ensure_ascii=False, indent=2)[:1500])


if __name__ == "__main__":
    complex_no = sys.argv[1] if len(sys.argv) > 1 else "971"
    asyncio.run(main(complex_no))
