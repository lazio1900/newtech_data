"""
KB부동산 API 디스커버리 CLI 도구.

kbland.kr을 Playwright로 탐색하여 내부 API 엔드포인트를 발견합니다.

사용법:
    python -m scripts.run_api_discovery
    python -m scripts.run_api_discovery --complex-url "https://kbland.kr/c/23511"
    python -m scripts.run_api_discovery --output report.json
"""
import argparse
import asyncio
import json
import logging
import sys
import os

# 프로젝트 루트를 path에 추가
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from src.browser.api_discovery import KBApiDiscovery


def setup_logging(verbose: bool = False):
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )


async def main(args):
    discovery = KBApiDiscovery()

    print("=" * 60)
    print("KB부동산 API Discovery Tool")
    print("=" * 60)
    print()

    report = await discovery.discover(
        complex_url=args.complex_url,
        wait_seconds=args.wait,
    )

    # 결과 출력
    print(f"\n총 캡처된 요청: {report['total_requests_captured']}")
    print(f"유니크 엔드포인트: {report['unique_endpoints']}")
    print()

    # 카테고리별 요약
    print("--- 카테고리별 엔드포인트 ---")
    for category, endpoints in report.get("endpoints_by_category", {}).items():
        print(f"\n[{category}] ({len(endpoints)}개 요청)")
        for ep in endpoints:
            print(f"  {ep['method']} {ep['domain']}{ep['path']}")
            if ep.get("query_params"):
                print(f"    params: {ep['query_params']}")
            if ep.get("post_data"):
                preview = ep["post_data"][:200]
                print(f"    body: {preview}")
            print(f"    status: {ep.get('status')}")

    # 유니크 엔드포인트 요약
    print("\n--- 유니크 엔드포인트 요약 ---")
    for ep in report.get("unique_endpoint_summary", []):
        print(f"  [{ep['category']}] {ep['method']} {ep['domain']}{ep['path']} (x{ep['hit_count']})")

    # 파일로 저장
    if args.output:
        # response_body_preview만 유지 (full body 제거)
        output_report = json.dumps(report, indent=2, ensure_ascii=False, default=str)
        with open(args.output, "w", encoding="utf-8") as f:
            f.write(output_report)
        print(f"\n리포트 저장됨: {args.output}")

    # 브라우저 정리
    from src.browser.session_manager import BrowserSessionManager
    await BrowserSessionManager.shutdown()


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description="KB부동산 API Discovery Tool")
    parser.add_argument(
        "--complex-url",
        type=str,
        default=None,
        help="특정 단지 페이지 URL (예: https://kbland.kr/c/23511)",
    )
    parser.add_argument(
        "--output", "-o",
        type=str,
        default=None,
        help="리포트 출력 파일 경로 (JSON)",
    )
    parser.add_argument(
        "--wait",
        type=float,
        default=5.0,
        help="각 페이지 대기 시간 (초, 기본: 5.0)",
    )
    parser.add_argument(
        "--verbose", "-v",
        action="store_true",
        help="상세 로그 출력",
    )

    args = parser.parse_args()
    setup_logging(args.verbose)
    asyncio.run(main(args))
