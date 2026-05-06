"""KB부동산 단지 페이지의 '주변시설' 탭을 자동 클릭하면서 호출되는 API를 캡처.

usage:
    python scripts/probe_facility_apis.py 1046
    python scripts/probe_facility_apis.py 1046 --output facility_capture.json
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from playwright.async_api import async_playwright


async def main(complex_id: str, output: str, wait_seconds: float = 8.0) -> None:
    captured: list[dict[str, Any]] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        context = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1280, "height": 900},
        )
        page = await context.new_page()

        async def on_response(resp):
            url = resp.url
            if "api.kbland.kr" not in url:
                return
            try:
                body = await resp.text()
                body_preview = body[:5000]
            except Exception:
                body_preview = ""
            captured.append({
                "method": resp.request.method,
                "url": url,
                "status": resp.status,
                "post_data": resp.request.post_data,
                "response_preview": body_preview,
            })

        page.on("response", on_response)

        print(f"[probe] navigating to https://kbland.kr/c/{complex_id}")
        await page.goto(f"https://kbland.kr/c/{complex_id}", wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(wait_seconds)

        # 주변시설 / 학군 / 교통 / 안전 / 충전 등 다양한 키워드로 탭 클릭 시도
        tab_keywords = [
            "주변시설", "주변", "입지", "주변환경",
            "학군", "교육", "학교",
            "교통", "지하철", "버스",
            "안전", "CCTV", "방범",
            "병원", "의료",
            "편의시설", "마트", "은행",
            "전기차", "충전소", "충전",
            "공원", "녹지",
        ]
        clicked: list[str] = []
        for kw in tab_keywords:
            try:
                el = page.locator(f"text=/{kw}/").first
                if await el.is_visible(timeout=1500):
                    print(f"[probe] click '{kw}'")
                    await el.click(timeout=2000)
                    await asyncio.sleep(2.5)
                    clicked.append(kw)
            except Exception:
                pass

        # 페이지 끝까지 스크롤 (lazy-load 시설 목록 로딩)
        try:
            for _ in range(10):
                await page.mouse.wheel(0, 1500)
                await asyncio.sleep(0.4)
        except Exception:
            pass

        await asyncio.sleep(2.0)
        await browser.close()

    print(f"\n[probe] clicked tabs: {clicked}")
    print(f"[probe] captured {len(captured)} api.kbland.kr responses")

    # 유니크 endpoint 분류
    unique: dict[str, dict] = {}
    for c in captured:
        u = urlparse(c["url"])
        key = f"{c['method']} {u.path}"
        if key not in unique:
            unique[key] = {
                "method": c["method"],
                "path": u.path,
                "sample_params": parse_qs(u.query),
                "sample_post_data": c["post_data"],
                "status": c["status"],
                "response_preview": c["response_preview"][:600],
                "hit_count": 0,
            }
        unique[key]["hit_count"] += 1

    # 시설 관련 의심 endpoint 우선 표시
    facility_keywords = ["lifeAround", "facility", "school", "subway", "hospital",
                         "cctv", "charge", "ev", "park", "infra", "around",
                         "lifeInfra", "transport", "edu", "medical", "safety"]

    print("\n=== 시설 관련 의심 endpoint ===")
    for key, info in unique.items():
        if any(kw.lower() in key.lower() for kw in facility_keywords):
            print(f"\n  ★ {key}")
            print(f"    params: {dict(list(info['sample_params'].items())[:5])}")
            print(f"    response[:200]: {info['response_preview'][:200]}")

    print("\n=== 그 외 endpoint (참고) ===")
    for key, info in unique.items():
        if not any(kw.lower() in key.lower() for kw in facility_keywords):
            print(f"  {key}  (hits={info['hit_count']})")

    # 전체 결과 JSON 저장
    out_path = Path(output)
    out_path.write_text(
        json.dumps(
            {
                "complex_id": complex_id,
                "clicked_tabs": clicked,
                "total_captured": len(captured),
                "unique_endpoints": list(unique.values()),
                "all_captures": captured,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )
    print(f"\n[probe] saved → {out_path}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("complex_id", help="KB 단지 일련번호 (예: 1046)")
    parser.add_argument("--output", "-o", default="facility_discovery.json")
    parser.add_argument("--wait", type=float, default=8.0)
    args = parser.parse_args()
    asyncio.run(main(args.complex_id, args.output, args.wait))
