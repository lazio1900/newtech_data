"""KB 단지 주변 시설 (학군/지하철/병원) 통합 커넥터.

학군: complexSchool/list (단지기본일련번호 기반, 거리 포함)
지하철: honeyLocation/subwayMarkerList (좌표 박스 기반, 거리 직접 계산)
병원: honeyLocation/hospitalMarkerList (좌표 박스 기반, 거리 직접 계산)
"""
from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional

from src.connectors.base import ParserError
from src.connectors.kb_base import KBBaseConnector
from src.connectors.kb_endpoints import (
    COMPLEX_SCHOOL_LIST,
    HOSPITAL_MARKER_LIST,
    SUBWAY_MARKER_LIST,
    KBEndpoint,
)

logger = logging.getLogger(__name__)


SCHOOL_PROCESS_CODES: Dict[str, str] = {
    "01": "kindergarten",
    "02": "preschool",
    "03": "elementary",
    "04": "middle",
    "05": "high",
}


def _haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> int:
    """두 좌표 사이의 거리(m)."""
    R = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmd = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlmd / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return int(R * c)


def _safe_int(v) -> Optional[int]:
    if v is None:
        return None
    try:
        return int(round(float(v)))
    except (ValueError, TypeError):
        return None


def _safe_float(v) -> Optional[float]:
    if v is None:
        return None
    try:
        return float(v)
    except (ValueError, TypeError):
        return None


class KBFacilityConnector(KBBaseConnector):
    """학군 + 지하철 + 병원을 통합 수집."""

    def __init__(self, name: str = "kb_facility", rate_limit_per_minute: int = 30):
        super().__init__(name=name, rate_limit_per_minute=rate_limit_per_minute)

    def _build_http_params(self, **kw):
        # 추상 메서드 충족용 — 실제 호출은 fetch_* 가 직접 endpoint 지정
        return (COMPLEX_SCHOOL_LIST, kw)

    def _build_browser_config(self, **kw):
        return ("", "", None)

    def parse(self, raw):  # 미사용
        return raw

    # ---------- 학군 ----------
    async def fetch_schools(self, kb_complex_id: str) -> List[Dict[str, Any]]:
        """5개 학교과정 모두 수집."""
        out: List[Dict[str, Any]] = []
        for code, sub_type in SCHOOL_PROCESS_CODES.items():
            try:
                raw = await self._fetch_via_http(
                    COMPLEX_SCHOOL_LIST,
                    {"단지기본일련번호": kb_complex_id, "학교과정분류구분": code},
                )
                items = raw.get("dataBody", {}).get("data") or []
                for it in items:
                    if not isinstance(it, dict):
                        continue
                    name = (
                        it.get("학교명") or it.get("어린이집명")
                        or it.get("유치원명") or it.get("교육기관명")
                    )
                    if not name:
                        continue
                    eid = it.get("학교식별자") or it.get("어린이집식별자") or it.get("유치원식별자")
                    out.append({
                        "facility_type": "school",
                        "sub_type": sub_type,
                        "external_id": str(eid) if eid else None,
                        "name": name,
                        "address": it.get("주소"),
                        "phone": it.get("전화번호"),
                        "distance_m": _safe_int(it.get("거리")),
                        "lat": _safe_float(it.get("wgs84위도")),
                        "lng": _safe_float(it.get("wgs84경도")),
                        "meta": it,
                    })
            except Exception as e:
                logger.warning(f"[kb_facility] school {code} for complex {kb_complex_id}: {e}")
        return out

    # ---------- 좌표 박스 기반 (지하철/병원) ----------
    async def _fetch_marker(
        self,
        endpoint: KBEndpoint,
        lat: float,
        lng: float,
        delta: float = 0.012,
    ) -> List[Dict[str, Any]]:
        params = {
            "startLat": lat - delta,
            "startLng": lng - delta,
            "endLat": lat + delta,
            "endLng": lng + delta,
            "zoomLevel": 16,
        }
        raw = await self._fetch_via_http(endpoint, params)
        return raw.get("dataBody", {}).get("data") or []

    async def fetch_subways(
        self, lat: float, lng: float, delta: float = 0.012
    ) -> List[Dict[str, Any]]:
        items = await self._fetch_marker(SUBWAY_MARKER_LIST, lat, lng, delta)
        out: List[Dict[str, Any]] = []
        for it in items:
            slat = _safe_float(it.get("wgs84위도"))
            slng = _safe_float(it.get("wgs84경도"))
            distance = _haversine_m(lat, lng, slat, slng) if slat and slng else None
            eid = it.get("지하철역식별자")
            out.append({
                "facility_type": "subway",
                "sub_type": it.get("지하철호선명"),  # e.g., "서울-4호선"
                "external_id": str(eid) if eid else None,
                "name": it.get("지하철역명"),
                "address": None,
                "phone": None,
                "distance_m": distance,
                "lat": slat,
                "lng": slng,
                "meta": it,
            })
        return out

    async def fetch_hospitals(
        self, lat: float, lng: float, delta: float = 0.012
    ) -> List[Dict[str, Any]]:
        items = await self._fetch_marker(HOSPITAL_MARKER_LIST, lat, lng, delta)
        out: List[Dict[str, Any]] = []
        for it in items:
            hlat = _safe_float(it.get("wgs84위도"))
            hlng = _safe_float(it.get("wgs84경도"))
            distance = _haversine_m(lat, lng, hlat, hlng) if hlat and hlng else None
            # 병원은 KB 가 고유 ID 없음 → 좌표+종류로 합성 ID (UNIQUE 충돌 방지)
            sub = it.get("대표종류") or "일반"
            synthetic_id = (
                f"hosp_{sub}_{hlat:.5f}_{hlng:.5f}"
                if hlat is not None and hlng is not None
                else None
            )
            out.append({
                "facility_type": "hospital",
                "sub_type": sub,
                "external_id": synthetic_id,
                "name": it.get("병원목록"),
                "address": None,
                "phone": None,
                "distance_m": distance,
                "lat": hlat,
                "lng": hlng,
                "meta": it,
            })
        return out

    async def fetch_all(
        self,
        kb_complex_id: str,
        lat: Optional[float] = None,
        lng: Optional[float] = None,
    ) -> List[Dict[str, Any]]:
        """모든 시설 종합. lat/lng 가 없으면 학군만 수집."""
        out: List[Dict[str, Any]] = []
        out.extend(await self.fetch_schools(kb_complex_id))
        if lat is not None and lng is not None:
            try:
                out.extend(await self.fetch_subways(lat, lng))
            except Exception as e:
                logger.warning(f"[kb_facility] subway for complex {kb_complex_id}: {e}")
            try:
                out.extend(await self.fetch_hospitals(lat, lng))
            except Exception as e:
                logger.warning(f"[kb_facility] hospital for complex {kb_complex_id}: {e}")
        return out
