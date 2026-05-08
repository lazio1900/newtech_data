"""
KB 실거래가 데이터 수집 커넥터.

KB부동산에서 아파트 단지별 실거래가 데이터를 수집합니다.
기존 MolitTransactionConnector(국토교통부 OpenAPI)와 독립적으로 동작합니다.
"""
from typing import Any, Callable, Dict, List, Optional, Tuple
import logging

from src.connectors.kb_base import KBBaseConnector
from src.connectors.kb_endpoints import KBEndpoint, COMPLEX_PRESALE_PRICES
from src.connectors.base import ParserError

logger = logging.getLogger(__name__)


class KBTransactionConnector(KBBaseConnector):
    """
    KB 실거래가 커넥터.

    수집 데이터: 계약일, 거래가, 전용면적, 층, 해제여부
    단위: 만원 → 원으로 변환하여 저장
    """

    def __init__(self, db_session=None, rate_limit_per_minute: int = 20):
        super().__init__(
            name="KBTransactionConnector",
            rate_limit_per_minute=rate_limit_per_minute,
            db_session=db_session,
        )

    def _build_http_params(self, **kwargs) -> Tuple[KBEndpoint, dict]:
        """실거래가 API 파라미터 빌드 — preSalePrices endpoint.

        거래구분: 1=매매, 2=전세, 3=월세, 0=전체. 매매만 우선.
        페이지갯수 50 — 보통 한 면적당 매매 거래가 수십건이므로 충분.
        """
        complex_id = kwargs["complex_id"]
        area_id = kwargs.get("area_id")
        kb_complex_id = self._resolve_kb_complex_id(complex_id)

        params = {
            "단지기본일련번호": kb_complex_id,
            "거래구분": "1",  # 1=매매
            "면적그룹여부": "0",
            "현재페이지": "1",
            "첫페이지갯수": "50",
            "페이지갯수": "50",
        }
        if area_id:
            from src.models.complex import Area
            area_obj = self.db.query(Area).get(area_id)
            if area_obj and area_obj.kb_area_code:
                params["면적일련번호"] = area_obj.kb_area_code
        return (COMPLEX_PRESALE_PRICES, params)

    def _build_browser_config(self, **kwargs) -> Tuple[str, str, Optional[Callable]]:
        """실거래가 브라우저 폴백 설정"""
        complex_id = kwargs["complex_id"]
        kb_complex_id = self._resolve_kb_complex_id(complex_id)

        page_url = f"https://kbland.kr/map?complexNo={kb_complex_id}"
        api_pattern = "deal"

        async def interact(page):
            """실거래가 탭 클릭"""
            tab_selectors = [
                'text="실거래가"',
                'text="실거래"',
                '[data-tab="deal"]',
                'button:has-text("실거래")',
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
        """KB preSalePrices 응답 파싱.

        응답 구조:
        {
            "dataBody": {
                "data": {
                    "dataList": [
                        {
                            "계약년월일": "20260401",
                            "물건거래구분": "1",          # 1=매매
                            "매매실거래금액": 70000,      # 만원
                            "해당층수": "6",
                            "전용면적": "84",
                            "계약취소여부": "0",
                            "수집일련번호": 12345,         # unique key
                            ...
                        }
                    ]
                }
            }
        }
        """
        try:
            data = raw_data
            if isinstance(data, dict):
                data = data.get("dataBody", data)
                if isinstance(data, dict):
                    data = data.get("data", data)

            deal_list = []
            if isinstance(data, dict):
                deal_list = data.get("dataList") or []
            elif isinstance(data, list):
                deal_list = data

            parsed: List[Dict[str, Any]] = []
            for item in deal_list:
                if not isinstance(item, dict):
                    continue

                # 매매만 (거래구분=1) — 안전 필터
                if str(item.get("물건거래구분", "")) != "1":
                    continue

                # 계약일 — "20260401" → "2026-04-01"
                d = str(item.get("계약년월일") or "")
                if len(d) != 8 or not d.isdigit():
                    continue
                contract_date = f"{d[:4]}-{d[4:6]}-{d[6:8]}"

                # 매매실거래금액 (만원 → 원)
                amt_man = item.get("매매실거래금액")
                if amt_man is None:
                    continue
                try:
                    price = int(float(amt_man)) * 10000
                except (ValueError, TypeError):
                    continue

                # 전용면적 (str → float)
                exclusive_m2 = 0.0
                try:
                    if item.get("전용면적") is not None:
                        exclusive_m2 = float(item["전용면적"])
                except (ValueError, TypeError):
                    pass

                # 층
                floor = None
                try:
                    f_str = item.get("해당층수")
                    if f_str is not None and str(f_str).strip():
                        floor = int(float(f_str))
                except (ValueError, TypeError):
                    pass

                is_cancelled = str(item.get("계약취소여부", "0")) == "1"

                parsed.append({
                    "contract_date": contract_date,
                    "price": price,
                    "exclusive_m2": exclusive_m2,
                    "floor": floor,
                    "is_cancelled": is_cancelled,
                    "source": "kb",
                    "external_id": str(item.get("수집일련번호") or ""),
                })

            return parsed

        except Exception as e:
            raise ParserError(f"Failed to parse KB transaction data: {e}")

    def _extract_date(self, item: dict) -> Optional[str]:
        """거래 항목에서 날짜 추출"""
        # 단일 날짜 필드
        for key in ["dealDate", "contract_date", "거래일", "계약일", "tradeDate"]:
            if key in item and item[key]:
                return self._parse_date(str(item[key]))

        # 년/월/일 분리된 필드
        year = item.get("년") or item.get("year") or item.get("dealYear")
        month = item.get("월") or item.get("month") or item.get("dealMonth")
        day = item.get("일") or item.get("day") or item.get("dealDay")
        if year and month:
            day = day or "1"
            return f"{str(year).zfill(4)}-{str(month).zfill(2)}-{str(day).zfill(2)}"

        return None

    def _extract_transaction_price(self, item: dict) -> Optional[int]:
        """거래가 추출 (만원 → 원 변환)"""
        for key in ["dealAmt", "price", "거래금액", "거래가", "tradeAmt"]:
            if key in item and item[key] is not None:
                return self._to_won(item[key])
        return None

    @staticmethod
    def _extract_float(item: dict, keys: List[str]) -> Optional[float]:
        """여러 후보 키에서 float 추출"""
        for key in keys:
            if key in item and item[key] is not None:
                try:
                    return float(str(item[key]).replace(",", "").strip())
                except (ValueError, TypeError):
                    continue
        return None

    @staticmethod
    def _extract_int(item: dict, keys: List[str]) -> Optional[int]:
        """여러 후보 키에서 int 추출"""
        for key in keys:
            if key in item and item[key] is not None:
                try:
                    return int(str(item[key]).replace(",", "").strip())
                except (ValueError, TypeError):
                    continue
        return None

    @staticmethod
    def _extract_cancel_status(item: dict) -> bool:
        """해제 여부 추출"""
        for key in ["cancelYn", "is_cancelled", "해제여부", "cancelDealYn"]:
            if key in item:
                val = str(item[key]).strip().upper()
                return val in ("Y", "TRUE", "1", "해제")
        return False
