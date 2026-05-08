"""OpenStreetMap Overpass API 기반 자연환경 시설 (공원/녹지/하천) 수집.

KB API 가 제공하지 않는 자연환경 데이터를 OSM 에서 가져온다.
- leisure=park / garden / playground
- natural=wood / grassland / water
- waterway=river / stream

API: https://overpass-api.de/api/interpreter (인증 불필요, rate limit ~720/min)
응답: way / relation 단위. way 는 center 좌표 (out center).
"""
from __future__ import annotations

import logging
import math
from typing import Any, Dict, List, Optional

import httpx

logger = logging.getLogger(__name__)


OVERPASS_URL = "https://overpass-api.de/api/interpreter"


def _haversine_m(lat1: float, lng1: float, lat2: float, lng2: float) -> int:
    R = 6371000.0
    phi1 = math.radians(lat1)
    phi2 = math.radians(lat2)
    dphi = math.radians(lat2 - lat1)
    dlmd = math.radians(lng2 - lng1)
    a = math.sin(dphi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(dlmd / 2) ** 2
    c = 2 * math.atan2(math.sqrt(a), math.sqrt(1 - a))
    return int(R * c)


def _classify_sub_type(tags: Dict[str, Any]) -> str:
    """OSM 태그 → sub_type."""
    leisure = tags.get("leisure")
    natural = tags.get("natural")
    waterway = tags.get("waterway")
    if leisure == "park":
        return "park"
    if leisure == "garden":
        return "garden"
    if leisure == "playground":
        return "playground"
    if natural in ("wood", "forest"):
        return "forest"
    if natural in ("grassland", "scrub"):
        return "grassland"
    if natural == "water":
        return "water"
    if waterway in ("river", "stream"):
        return "river"
    return leisure or natural or waterway or "other"


class OSMNatureConnector:
    """단지 좌표 주변 자연환경(공원/녹지/하천) 수집."""

    def __init__(self, timeout_seconds: int = 30):
        self.timeout_seconds = timeout_seconds

    async def fetch_parks(
        self,
        lat: float,
        lng: float,
        radius_m: int = 1000,
    ) -> List[Dict[str, Any]]:
        """단지 좌표 주변 자연환경 시설.

        반환: facility 정규화 dict 리스트
              [{facility_type, sub_type, external_id, name, distance_m, lat, lng, meta}, ...]
        """
        # Overpass QL — way + relation 둘 다, center 포함
        query = f"""
        [out:json][timeout:{self.timeout_seconds}];
        (
          way["leisure"~"park|garden|playground"](around:{radius_m},{lat},{lng});
          relation["leisure"~"park|garden"](around:{radius_m},{lat},{lng});
          way["natural"~"wood|forest|grassland|water"](around:{radius_m},{lat},{lng});
          way["waterway"~"river|stream"](around:{radius_m},{lat},{lng});
        );
        out center tags;
        """

        async with httpx.AsyncClient(timeout=self.timeout_seconds) as client:
            try:
                resp = await client.post(
                    OVERPASS_URL,
                    data={"data": query},
                    headers={"User-Agent": "newtech-data/1.0 (kb-estate-collector)"},
                )
                resp.raise_for_status()
                data = resp.json()
            except Exception as e:
                logger.warning(f"[osm_nature] overpass error: {e}")
                return []

        elements = data.get("elements", [])
        out: List[Dict[str, Any]] = []
        for el in elements:
            tags = el.get("tags") or {}
            # 좌표: way 는 center, node 는 lat/lon
            center = el.get("center") or {}
            elat = center.get("lat") or el.get("lat")
            elng = center.get("lon") or el.get("lon")
            if elat is None or elng is None:
                continue

            name = (
                tags.get("name:ko")
                or tags.get("name")
                or tags.get("name:en")
                or "(이름없음)"
            )
            sub_type = _classify_sub_type(tags)
            distance = _haversine_m(lat, lng, float(elat), float(elng))

            external_id = f"osm_{el.get('type')}_{el.get('id')}"
            out.append({
                "facility_type": "park",
                "sub_type": sub_type,
                "external_id": external_id,
                "name": name,
                "address": None,
                "phone": None,
                "distance_m": distance,
                "lat": float(elat),
                "lng": float(elng),
                "meta": {"osm_type": el.get("type"), "osm_id": el.get("id"), "tags": tags},
            })

        # 거리 오름차순 정렬, 동일 외부 ID 중복 제거
        seen = set()
        unique: List[Dict[str, Any]] = []
        for item in sorted(out, key=lambda x: x["distance_m"] or 0):
            if item["external_id"] in seen:
                continue
            seen.add(item["external_id"])
            unique.append(item)
        return unique
