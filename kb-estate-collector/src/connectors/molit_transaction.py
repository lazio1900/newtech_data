"""
국토교통부 실거래가 OpenAPI 커넥터.

공공데이터포털(data.go.kr) 의 RTMSDataSvcAptTradeDev (아파트 매매 실거래 상세) 호출.
- LAWD_CD (시군구 5자리) + DEAL_YMD (YYYYMM) 단위 조회. 한 호출당 한 월·한 시군구.
- 응답은 XML. numOfRows / pageNo 로 페이징.
"""
from __future__ import annotations

import logging
import os
import xml.etree.ElementTree as ET  # noqa: N817  표준 idiom
from typing import Any, Dict, List, Optional

import httpx

from src.connectors.base import BaseConnector, NetworkError, ParserError

logger = logging.getLogger(__name__)


class MolitTransactionConnector(BaseConnector):
    """국토교통부 실거래가 OpenAPI 커넥터 (XML)."""

    BASE_URL = "https://apis.data.go.kr/1613000/RTMSDataSvcAptTradeDev/getRTMSDataSvcAptTradeDev"
    DEFAULT_ROWS = 1000  # API 페이지당 최대치 (실측 시 조정)

    def __init__(self, api_key: Optional[str] = None, rate_limit_per_minute: int = 60):
        super().__init__(
            name="MolitTransactionConnector",
            rate_limit_per_minute=rate_limit_per_minute,
        )
        # decoding 키를 그대로 사용 — httpx 의 params 가 URL encoding 책임
        self.api_key = api_key or os.environ.get("MOLIT_API_KEY")
        if not self.api_key:
            raise ValueError("MOLIT_API_KEY not set in env")

    def fetch(self, region_code: str, contract_month: str, **kwargs) -> Dict[str, Any]:
        """
        region_code: 시군구 LAWD_CD 5자리 (예: '11680' 강남구)
        contract_month: 'YYYYMM' (예: '202604')
        """
        all_items: List[dict] = []
        page = 1
        while True:
            params = {
                "serviceKey": self.api_key,
                "LAWD_CD": region_code,
                "DEAL_YMD": contract_month,
                "pageNo": page,
                "numOfRows": self.DEFAULT_ROWS,
            }
            try:
                with httpx.Client(timeout=30.0) as cl:
                    resp = cl.get(self.BASE_URL, params=params)
            except httpx.RequestError as e:
                raise NetworkError(f"MOLIT request failed: {e}") from e
            if resp.status_code != 200:
                raise NetworkError(f"MOLIT HTTP {resp.status_code}: {resp.text[:200]}")

            try:
                root = ET.fromstring(resp.text)
            except ET.ParseError as e:
                raise ParserError(f"MOLIT XML parse failed: {e}; body={resp.text[:300]}") from e

            # API 오류 체크 — data.go.kr 신/구 응답 모두 OK 코드 허용
            result_code = root.findtext(".//resultCode") or "000"
            if result_code not in ("00", "000"):
                msg = root.findtext(".//resultMsg") or "?"
                raise NetworkError(f"MOLIT API error code={result_code} msg={msg}")

            items = root.findall(".//item")
            for it in items:
                d = {child.tag: (child.text or "").strip() for child in it}
                all_items.append(d)

            total = int(root.findtext(".//totalCount") or "0")
            if not items or page * self.DEFAULT_ROWS >= total:
                break
            page += 1
            if page > 30:  # safety cap (30 * 1000 rows = 30,000건)
                logger.warning(
                    f"{self.name}: pageNo cap reached for {region_code} {contract_month}"
                )
                break

        logger.info(f"{self.name}: {region_code} {contract_month} → {len(all_items)} transactions")
        return {
            "data": all_items,
            "metadata": {
                "source": "molit",
                "region_code": region_code,
                "contract_month": contract_month,
            },
        }

    def parse(self, raw_data: Any) -> List[Dict[str, Any]]:
        """
        MOLIT XML item 목록을 transactions 스키마로 변환.
        - 거래금액(만원, 콤마) → 원
        - 년/월/일 → contract_date
        - 전용면적 → exclusive_m2 (float)
        - 층 → floor (int|None)
        - 단지명·법정동 등은 단지 매칭용 메타로 별도 보관
        """
        items = raw_data if isinstance(raw_data, list) else raw_data.get("data", [])
        parsed: List[Dict[str, Any]] = []
        for item in items:
            try:
                price_man = int(str(item.get("dealAmount", "")).replace(",", "").strip())
                exclusive_m2 = float(item.get("excluUseAr") or 0)
                if exclusive_m2 <= 0:
                    continue
                y = int(item.get("dealYear") or 0)
                m = int(item.get("dealMonth") or 0)
                d = int(item.get("dealDay") or 0)
                if not (y and m and d):
                    continue
                floor_str = item.get("floor")
                floor = int(floor_str) if floor_str and floor_str.lstrip("-").isdigit() else None
                is_cancelled = bool((item.get("cdealType") or "").strip())
                parsed.append(
                    {
                        "contract_date": f"{y:04d}-{m:02d}-{d:02d}",
                        "price": price_man * 10000,
                        "exclusive_m2": exclusive_m2,
                        "floor": floor,
                        "is_cancelled": is_cancelled,
                        "source": "molit",
                        "source_id": item.get("aptSeq") or None,  # 단지 매칭 키 (sggCd-bonbun)
                        # 단지 매칭 메타 (DB 저장 안 함, 후처리용)
                        "_apt_name": item.get("aptNm") or "",
                        "_dong": item.get("umdNm") or "",
                        "_jibun": item.get("jibun") or "",
                        "_sgg_cd": item.get("sggCd") or "",
                    }
                )
            except (ValueError, TypeError) as e:
                logger.warning(f"{self.name}: parse error {e}, item={item}")
                continue
        return parsed
