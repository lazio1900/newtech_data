"""KB 단지 페이지의 '주변시설' 영역을 deep probing.

- 모든 텍스트 라벨(학군/교통/안전/편의/의료/공원/충전 등)에 대해 클릭 시도
- role=tab / role=button / a 태그 등 다양한 selector
- 사이드 패널 펼치기 + 스크롤 + 호버

usage: python scripts/probe_facility_deep.py 1046 -o facility_deep.json
"""
from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from urllib.parse import parse_qs, urlparse

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from playwright.async_api import async_playwright


CATEGORY_KEYWORDS = [
    # 큰 영역 진입
    "주변시설", "주변환경", "입지", "주변",
    # 시설 카테고리
    "학군", "교육", "학교", "어린이집", "유치원",
    "교통", "지하철", "버스", "정류장", "역",
    "안전", "CCTV", "방범", "범죄",
    "의료", "병원", "약국", "응급",
    "편의", "마트", "은행", "관공서", "주민센터",
    "전기차", "충전소", "충전",
    "공원", "녹지", "산책",
    "유해", "유해시설",
]


async def main(complex_id: str, output: str, wait: float = 5.0) -> None:
    captured: list[dict] = []

    async with async_playwright() as p:
        browser = await p.chromium.launch(headless=True)
        ctx = await browser.new_context(
            user_agent=(
                "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) "
                "AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36"
            ),
            viewport={"width": 1440, "height": 900},
        )
        page = await ctx.new_page()

        async def on_response(resp):
            url = resp.url
            if "api.kbland.kr" not in url:
                return
            try:
                body = await resp.text()
                preview = body[:5000]
            except Exception:
                preview = ""
            captured.append({
                "method": resp.request.method,
                "url": url,
                "status": resp.status,
                "post_data": resp.request.post_data,
                "response_preview": preview,
                "trigger": getattr(on_response, "current_label", "initial"),
            })

        on_response.current_label = "initial"  # type: ignore[attr-defined]
        page.on("response", on_response)

        print(f"[probe] navigating to https://kbland.kr/c/{complex_id}")
        await page.goto(f"https://kbland.kr/c/{complex_id}", wait_until="domcontentloaded", timeout=30000)
        await asyncio.sleep(wait)

        clicked: list[str] = []
        for kw in CATEGORY_KEYWORDS:
            on_response.current_label = kw  # type: ignore[attr-defined]

            # 다양한 locator 시도
            for selector in (
                f"role=tab[name=/{kw}/]",
                f"role=button[name=/{kw}/]",
                f"text=/{kw}/",
                f"a:has-text(\"{kw}\")",
                f"button:has-text(\"{kw}\")",
                f"li:has-text(\"{kw}\")",
            ):
                try:
                    el = page.locator(selector).first
                    if await el.count() == 0:
                        continue
                    if await el.is_visible(timeout=800):
                        await el.click(timeout=2000, force=True)
                        await asyncio.sleep(2.0)
                        clicked.append(f"{kw} via {selector}")
                        break
                except Exception:
                    continue

        # 한번 더 wait + scroll
        on_response.current_label = "scroll"  # type: ignore[attr-defined]
        try:
            for _ in range(15):
                await page.mouse.wheel(0, 1500)
                await asyncio.sleep(0.3)
        except Exception:
            pass
        await asyncio.sleep(2.0)

        await browser.close()

    print(f"\n[probe] clicked: {len(clicked)} attempts")
    print(f"[probe] captured: {len(captured)} responses")

    # 시설 후보 키워드를 path에 포함하는 endpoint
    facility_kw = ("school", "subway", "station", "hospital", "medical", "cctv",
                   "safety", "charge", "ev", "park", "infra", "around", "lifeAround",
                   "honeyLocation", "facility", "surround", "convenience", "edu", "transport")

    print("\n=== 시설 의심 endpoint (path 매칭) ===")
    seen = set()
    for c in captured:
        u = urlparse(c["url"])
        key = f"{c['method']} {u.path}"
        if key in seen:
            continue
        if any(kw.lower() in u.path.lower() for kw in facility_kw):
            seen.add(key)
            params = list(parse_qs(u.query).keys())
            preview = c["response_preview"][:160].replace("\n", " ")
            print(f"  {key}")
            print(f"    params: {params}")
            print(f"    trigger: {c.get('trigger')}")
            print(f"    resp[:160]: {preview}\n")

    Path(output).write_text(
        json.dumps({"clicked": clicked, "captures": captured}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"[probe] saved → {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("complex_id")
    parser.add_argument("--output", "-o", default="facility_deep.json")
    parser.add_argument("--wait", type=float, default=5.0)
    args = parser.parse_args()
    asyncio.run(main(args.complex_id, args.output, args.wait))
