"""KB부동산 단지 페이지의 '실거래가' 탭을 자동 클릭하면서 호출되는 API 캡처.

usage:
    python scripts/probe_transaction_apis.py 1016
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


async def main(complex_id: str, output: str, wait_seconds: float = 6.0) -> None:
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
                body_preview = body[:8000]
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

        # 실거래가 / 시세 / 거래 등 탭 클릭 시도
        tab_keywords = ["실거래가", "실거래", "거래", "시세", "매매가"]
        for kw in tab_keywords:
            try:
                el = page.get_by_text(kw, exact=False).first
                if await el.count() > 0:
                    print(f"[probe] clicking tab '{kw}'")
                    await el.click(timeout=3000)
                    await asyncio.sleep(3)
                    break
            except Exception as e:
                print(f"[probe] tab '{kw}' click failed: {e}")

        # 페이지 스크롤 + 추가 대기 (lazy load)
        for _ in range(3):
            await page.evaluate("window.scrollBy(0, 800)")
            await asyncio.sleep(1)

        await asyncio.sleep(2)
        await browser.close()

    # 거래/실거래/deal 관련 endpoint 만 필터
    keywords = ["deal", "거래", "trade", "transaction", "Hscm", "Price"]
    relevant = [
        c for c in captured
        if any(k in c["url"].lower() or k in c["url"] for k in keywords)
    ]

    print(f"\n[probe] total captured: {len(captured)}, transaction-related: {len(relevant)}")
    print("\n--- Transaction-related endpoints (unique paths) ---")
    seen_paths = set()
    for c in relevant:
        path = urlparse(c["url"]).path
        if path in seen_paths:
            continue
        seen_paths.add(path)
        qs = parse_qs(urlparse(c["url"]).query)
        print(f"  [{c['method']}] {path}")
        if qs:
            print(f"    query: {dict(qs)}")
        # 응답에 deal 들어가면 표시
        preview = c["response_preview"][:300].replace("\n", " ")
        print(f"    resp[:300]: {preview}")
        print()

    Path(output).write_text(json.dumps(captured, ensure_ascii=False, indent=2))
    print(f"[probe] full capture saved to {output}")


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("complex_id", help="KB 단지 ID (e.g., 1016)")
    parser.add_argument("--output", default="transaction_capture.json")
    args = parser.parse_args()
    asyncio.run(main(args.complex_id, args.output))
