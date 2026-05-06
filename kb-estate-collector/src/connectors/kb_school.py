"""KB 단지 학군(어린이집/유치원/초/중/고) 수집 커넥터."""
from __future__ import annotations

import logging
from typing import Any, Dict, List, Optional

from src.connectors.base import ParserError
from src.connectors.kb_base import KBBaseConnector
from src.connectors.kb_endpoints import COMPLEX_SCHOOL_LIST, KBEndpoint

logger = logging.getLogger(__name__)


# 학교과정분류구분 코드 → sub_type
SCHOOL_PROCESS_CODES: Dict[str, str] = {
    "01": "kindergarten",   # 어린이집 (가정/직장 등 어린이집)
    "02": "preschool",      # 유치원
    "03": "elementary",     # 초등학교
    "04": "middle",          # 중학교
    "05": "high",            # 고등학교
}


class KBSchoolConnector(KBBaseConnector):
    """단지 주변 학군 정보를 수집한다.

    KB API: /land-complex/complexSchool/list
    응답에 학교/어린이집명, 거리, 좌표, 식별자, 주소, 전화 등 포함.
    """

    def __init__(self, name: str = "kb_school", rate_limit_per_minute: int = 30):
        super().__init__(name=name, rate_limit_per_minute=rate_limit_per_minute)

    def _build_http_params(self, **kw):
        return (COMPLEX_SCHOOL_LIST, kw)

    def _build_browser_config(self, **kw):
        return ("", "", None)

    def parse(self, raw: Any) -> List[Dict[str, Any]]:
        """KB 응답 → 정규화된 시설 dict 리스트."""
        if not isinstance(raw, dict):
            raise ParserError(f"unexpected raw type: {type(raw)}")
        body = raw.get("dataBody", {}).get("data") or []
        if not isinstance(body, list):
            return []

        normalized: List[Dict[str, Any]] = []
        for item in body:
            if not isinstance(item, dict):
                continue
            # 어린이집/학교 모두 동일한 키를 갖지 않을 수 있음 — fallback 처리
            external_id = (
                item.get("학교식별자")
                or item.get("어린이집식별자")
                or item.get("유치원식별자")
            )
            name = (
                item.get("학교명")
                or item.get("어린이집명")
                or item.get("유치원명")
                or item.get("교육기관명")
            )
            if not name:
                continue
            normalized.append({
                "external_id": str(external_id) if external_id else None,
                "name": name,
                "address": item.get("주소"),
                "phone": item.get("전화번호"),
                "distance_m": _safe_int(item.get("거리")),
                "lat": _safe_float(item.get("wgs84위도")),
                "lng": _safe_float(item.get("wgs84경도")),
                "meta": item,
            })
        return normalized

    async def fetch(self, kb_complex_id: str, school_process: str) -> List[Dict[str, Any]]:
        """학교과정 단계별 시설 목록 수집.

        kb_complex_id: 단지기본일련번호
        school_process: '01'~'05'
        """
        if school_process not in SCHOOL_PROCESS_CODES:
            raise ValueError(f"unknown school_process: {school_process}")

        raw = await self._fetch_via_http(
            COMPLEX_SCHOOL_LIST,
            {
                "단지기본일련번호": kb_complex_id,
                "학교과정분류구분": school_process,
            },
        )
        return self.parse(raw)

    async def fetch_all(self, kb_complex_id: str) -> Dict[str, List[Dict[str, Any]]]:
        """5개 학교과정 모두 수집.

        반환: {'kindergarten': [...], 'preschool': [...], 'elementary': [...], ...}
        """
        result: Dict[str, List[Dict[str, Any]]] = {}
        for code, sub_type in SCHOOL_PROCESS_CODES.items():
            try:
                items = await self.fetch(kb_complex_id, code)
                result[sub_type] = items
            except Exception as e:
                logger.warning(
                    f"[kb_school] complex={kb_complex_id} process={code}({sub_type}) failed: {e}"
                )
                result[sub_type] = []
        return result


def _safe_int(v: Optional[Any]) -> Optional[int]:
    if v is None:
        return None
    try:
        return int(round(float(v)))
    except (ValueError, TypeError):
        return None


def _safe_float(v: Optional[Any]) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None
