"""
KB 매물/호가 데이터 수집 커넥터.

KB부동산에서 아파트 단지별 매물 정보를 수집합니다.
개인정보(연락처 등)는 수집하지 않습니다.
"""
from typing import Any, Callable, Dict, List, Optional, Tuple
from datetime import datetime
import logging

from src.connectors.kb_base import KBBaseConnector
from src.connectors.kb_endpoints import KBEndpoint, COMPLEX_LISTING
from src.connectors.base import ParserError

logger = logging.getLogger(__name__)

# 매물 상태 매핑 (KB 응답값 → 내부 상태)
STATUS_MAP = {
    "A": "active",
    "ACTIVE": "active",
    "active": "active",
    "Y": "active",
    "S": "sold",
    "SOLD": "sold",
    "sold": "sold",
    "R": "removed",
    "REMOVED": "removed",
    "removed": "removed",
    "D": "removed",
    "DELETED": "removed",
}


class KBListingConnector(KBBaseConnector):
    """
    KB 매물/호가 커넥터.

    수집 데이터: 매물ID, 호가, 전용면적, 층, 상태, 등록일
    주의: 공개된 호가 정보만 수집, 개인정보(연락처) 수집 금지
    """

    def __init__(self, db_session=None, rate_limit_per_minute: int = 20):
        super().__init__(
            name="KBListingConnector",
            rate_limit_per_minute=rate_limit_per_minute,
            db_session=db_session,
        )

    def _build_http_params(self, **kwargs) -> Tuple[KBEndpoint, dict]:
        """매물 API 직접 호출용 파라미터 빌드"""
        complex_id = kwargs["complex_id"]
        kb_complex_id = self._resolve_kb_complex_id(complex_id)

        params = {
            "hscmNo": kb_complex_id,
            "dealType": "01",  # 01: 매매
        }
        return (COMPLEX_LISTING, params)

    def _build_browser_config(self, **kwargs) -> Tuple[str, str, Optional[Callable]]:
        """매물 브라우저 폴백 설정"""
        complex_id = kwargs["complex_id"]
        kb_complex_id = self._resolve_kb_complex_id(complex_id)

        page_url = f"https://kbland.kr/map?complexNo={kb_complex_id}"
        api_pattern = "article"

        async def interact(page):
            """매물 탭 클릭"""
            tab_selectors = [
                'text="매물"',
                'text="호가"',
                '[data-tab="article"]',
                'button:has-text("매물")',
            ]
            for selector in tab_selectors:
                try:
                    el = page.locator(selector).first
                    if await el.is_visible(timeout=2000):
                        await el.click()
                        await page.wait_for_timeout(2000)
                        return
                except Exception:
                    continue

        return (page_url, api_pattern, interact)

    def parse(self, raw_data: Any) -> List[Dict[str, Any]]:
        """
        KB 매물 응답 파싱.
        개인정보(연락처, 중개사 정보 등)는 의도적으로 수집하지 않음.

        응답 구조 (API 디스커버리 후 확정 필요):
        {
            "dataBody": {
                "data": {
                    "articleList": [
                        {
                            "articleNo": "12345",
                            "dealAmt": 51000,        # 호가 (만원)
                            "excArea": 84.5,
                            "floor": 10,
                            "regDate": "20250101",
                            "articleStatus": "A",
                        },
                        ...
                    ]
                }
            }
        }
        """
        try:
            # 응답 구조 탐색
            data = raw_data
            if isinstance(data, dict):
                data = data.get("dataBody", data)
                if isinstance(data, dict):
                    data = data.get("data", data)

            # 매물 목록 추출
            article_list = []
            if isinstance(data, dict):
                for key in ["articleList", "list", "items", "매물목록", "articles"]:
                    if key in data and isinstance(data[key], list):
                        article_list = data[key]
                        break
            elif isinstance(data, list):
                article_list = data

            parsed = []
            for item in article_list:
                if not isinstance(item, dict):
                    continue

                listing = self._parse_single_listing(item)
                if listing:
                    parsed.append(listing)

            return parsed

        except Exception as e:
            raise ParserError(f"Failed to parse KB listing data: {e}")

    def _parse_single_listing(self, item: dict) -> Optional[Dict[str, Any]]:
        """단일 매물 항목 파싱 (개인정보 필터링 포함)"""
        # 매물 ID
        listing_id = None
        for key in ["articleNo", "listing_id", "매물번호", "articleId", "no"]:
            if key in item and item[key]:
                listing_id = f"KB{item[key]}"
                break
        if not listing_id:
            return None

        # 호가
        ask_price = None
        for key in ["dealAmt", "ask_price", "호가", "price", "askPrice"]:
            if key in item and item[key] is not None:
                ask_price = self._to_won(item[key])
                break
        if not ask_price:
            return None

        # 전용면적
        exclusive_m2 = None
        for key in ["excArea", "exclusive_m2", "전용면적", "exclusiveArea"]:
            if key in item and item[key] is not None:
                try:
                    exclusive_m2 = float(str(item[key]).replace(",", "").strip())
                except (ValueError, TypeError):
                    pass
                break

        # 층
        floor = None
        for key in ["floor", "층", "floorInfo"]:
            if key in item and item[key] is not None:
                try:
                    floor = int(str(item[key]).replace(",", "").strip())
                except (ValueError, TypeError):
                    pass
                break

        # 상태
        status = "active"
        for key in ["articleStatus", "status", "상태", "saleStatus"]:
            if key in item and item[key]:
                raw_status = str(item[key]).strip()
                status = STATUS_MAP.get(raw_status, "unknown")
                break

        # 등록일
        posted_at = None
        for key in ["regDate", "posted_at", "등록일", "createDate", "regDt"]:
            if key in item and item[key]:
                posted_at = self._parse_date(str(item[key]))
                break

        return {
            "source_listing_id": listing_id,
            "ask_price": ask_price,
            "exclusive_m2": exclusive_m2,
            "floor": floor,
            "status": status,
            "posted_at": posted_at,
            "source": "kb",
        }
