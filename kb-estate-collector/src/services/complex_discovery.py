"""
지역 기반 아파트 단지 자동 발견 서비스.

지역코드를 입력하면 KB부동산에서 해당 지역의 아파트 단지를 검색하고,
DB에 자동으로 등록합니다.
"""
import asyncio
import logging
from typing import Any, Dict, List, Optional

from sqlalchemy.orm import Session

from src.browser.session_manager import BrowserSessionManager
from src.browser.stealth import get_random_delay
from src.connectors.base import BrowserError, NetworkError
from src.connectors.kb_base import KBBaseConnector
from src.connectors.kb_endpoints import (
    COMPLEX_DETAIL,
    COMPLEX_SEARCH,
    REGION_DONG,
    REGION_SIGUNGU,
)
from src.models.complex import Area, Complex, PriorityLevel

logger = logging.getLogger(__name__)


class _DiscoveryConnector(KBBaseConnector):
    """ComplexDiscoveryService 전용 커넥터. _fetch_via_http만 사용."""

    def _build_http_params(self, **kwargs):
        return (COMPLEX_SEARCH, kwargs)

    def _build_browser_config(self, **kwargs):
        return ("https://kbland.kr/map", "", None)

    def parse(self, raw_data):
        return []

    def fetch(self, **kwargs):
        return {}


class ComplexDiscoveryService:
    """
    지역코드로 KB부동산에서 아파트 단지를 자동 발견/등록하는 서비스.

    Flow:
    1. KB에서 지역코드로 단지 목록 조회
    2. 각 단지의 면적 정보도 조회
    3. DB에 없는 단지는 Complex + Area 레코드 생성
    4. 이미 존재하는 단지는 스킵

    지역코드 형식:
    - 5자리: 시/군/구 (예: "11680" → 강남구)
    - 10자리: 법정동 (예: "1168000000")
    """

    def __init__(self, db_session: Session):
        self.db = db_session
        self._connector = _DiscoveryConnector(
            name="ComplexDiscovery",
            rate_limit_per_minute=20,
        )

    async def discover_complexes(self, region_code: str) -> Dict[str, Any]:
        """
        해당 지역의 아파트 단지 발견 및 DB 등록.

        Args:
            region_code: 법정동코드 (5 또는 10자리)

        Returns:
            {
                'region_code': str,
                'total_found': int,
                'new_registered': int,
                'already_exists': int,
                'complexes': [{ name, kb_complex_id, is_new }]
            }
        """
        logger.info(f"Starting complex discovery for region: {region_code}")

        # Step 1: KB에서 단지 목록 조회
        raw_complexes = await self._fetch_complex_list(region_code)
        logger.info(f"Found {len(raw_complexes)} complexes from KB")

        # Step 2: DB 등록
        results = {
            "region_code": region_code,
            "total_found": 0,
            "new_registered": 0,
            "already_exists": 0,
            "complexes": [],
        }

        for raw in raw_complexes:
            kb_id = self._extract_kb_id(raw)
            if not kb_id:
                continue

            # 기존 단지 확인
            existing = self.db.query(Complex).filter(Complex.kb_complex_id == kb_id).first()

            if existing:
                results["already_exists"] += 1
                # 이미 등록됐지만 dong_code 미보유면 detail 재호출 대상 (region_code 잘못 분류 정정용)
                results["complexes"].append(
                    {
                        "name": existing.name,
                        "kb_complex_id": kb_id,
                        "is_new": False,
                        "needs_enrich": existing.dong_code is None,
                    }
                )
                continue

            # 신규 단지 등록
            complex_obj = self._create_complex(raw, region_code, kb_id)
            if complex_obj:
                results["new_registered"] += 1
                results["complexes"].append(
                    {
                        "name": complex_obj.name,
                        "kb_complex_id": kb_id,
                        "is_new": True,
                    }
                )

        self.db.commit()
        results["total_found"] = results["new_registered"] + results["already_exists"]

        # 신규 + 기존 중 dong_code 미보유 단지 detail 호출 — dong_code/lat/lng 채우고 region_code 정정
        # KB 박스가 인근 시군구 단지도 같이 반환하므로 실제 region 으로 재분류 필요.
        # 기존 단지도 포함하는 이유: 옛날 등록된 단지가 detail 정정 없이 잘못된 region_code 로 남아있는 경우,
        # 다음 discover 호출로 잡힌 박스 안 단지면 자동으로 정정됨.
        to_enrich = [
            c["kb_complex_id"] for c in results["complexes"] if c["is_new"] or c.get("needs_enrich")
        ]
        if to_enrich:
            await self._enrich_new_complexes(to_enrich)

        logger.info(
            f"Discovery complete: {results['total_found']} found, "
            f"{results['new_registered']} new, {results['already_exists']} existing"
        )
        return results

    async def _enrich_new_complexes(self, kb_ids: List[str]) -> None:
        """신규 단지에 detail 호출 → dong_code/lat/lng/region_code 정정."""
        for kb_id in kb_ids:
            try:
                data = await self._connector._fetch_via_http(
                    COMPLEX_DETAIL,
                    {"단지기본일련번호": kb_id, "물건종류": "01"},
                )
                body = data.get("dataBody", {}).get("data", {})
                if not body:
                    continue
                dong_code = body.get("법정동코드") or body.get("dongCd")
                dong_name = body.get("읍면동명") or body.get("법정동명") or body.get("dongNm")
                lat = body.get("wgs84위도") or body.get("위도")
                lng = body.get("wgs84경도") or body.get("경도")

                c = self.db.query(Complex).filter(Complex.kb_complex_id == kb_id).first()
                if not c:
                    continue
                if dong_code:
                    c.dong_code = str(dong_code)
                    c.region_code = str(dong_code)[:5]  # 실제 region 으로 재분류
                if dong_name:
                    c.dong_name = dong_name
                if lat:
                    try:
                        c.lat = float(lat)
                    except (ValueError, TypeError):
                        pass
                if lng:
                    try:
                        c.lng = float(lng)
                    except (ValueError, TypeError):
                        pass
            except Exception as e:
                logger.warning(f"enrich {kb_id} failed: {e}")
        self.db.commit()

    async def _fetch_complex_list(self, region_code: str) -> List[dict]:
        """KB 의 법정동 리스트 + 좌표를 받아 각 법정동 중심 박스로 호출.

        과거 grid 12x12 (144 호출/시군구) 방식은 외곽 읍·면(예: 마산회원구 내서읍)을
        못 덮는 한계가 있었음. 법정동 단위로 KB 가 직접 알려주는 중심좌표를 쓰면
        시군구당 N 호출(보통 9~25) 로 누락 없이 커버.
        """
        sido_name = self._sido_name_for(region_code)

        # 1) 시군구 메타 → 시군구명 매칭
        try:
            sg_data = await self._connector._fetch_via_http(REGION_SIGUNGU, {"시도명": sido_name})
            sigungu_list = sg_data.get("dataBody", {}).get("data", [])
        except Exception as e:
            logger.warning(f"시군구 조회 실패 {region_code}: {e}")
            return await self._fetch_complex_list_via_browser(region_code)

        sigungu_name = None
        for sg in sigungu_list:
            if sg.get("법정동코드", "").startswith(region_code[:5]):
                sigungu_name = sg.get("시군구명")
                break
        if not sigungu_name:
            logger.warning(
                f"시군구명을 찾을 수 없음: {region_code}. 알 수 없는 행정코드일 수 있음."
            )
            return []

        # 2) 시군구 → 법정동 리스트 (각 법정동 wgs84 중심좌표 포함)
        try:
            dong_data = await self._connector._fetch_via_http(
                REGION_DONG, {"시도명": sido_name, "시군구명": sigungu_name}
            )
            dong_list = dong_data.get("dataBody", {}).get("data", [])
        except Exception as e:
            logger.warning(f"법정동 조회 실패 {region_code} ({sigungu_name}): {e}")
            return await self._fetch_complex_list_via_browser(region_code)

        # 10자리 법정동 코드 입력이면 해당 법정동만 처리
        if len(region_code) >= 10:
            dong_list = [
                d for d in dong_list if d.get("법정동코드", "").startswith(region_code[:10])
            ]
        if not dong_list:
            logger.warning(f"법정동 리스트 비어있음: {region_code} ({sigungu_name})")
            return []

        # 3) 각 법정동 중심 ± 0.025 박스로 단지 검색 (반경 ~2.5km)
        half = 0.025
        seen_kb_ids: set = set()
        all_complexes: List[dict] = []
        success_dongs = 0

        for d in dong_list:
            try:
                lat = float(d.get("wgs84중심위도", 0))
                lng = float(d.get("wgs84중심경도", 0))
            except (TypeError, ValueError):
                continue
            if not (lat and lng):
                continue
            params = {
                "selectCode": "1,2,3",
                "zoomLevel": 16,
                "물건종류": "01",
                "거래유형": "1,2,3",
                "webCheck": "Y",
                "startLat": lat - half,
                "startLng": lng - half,
                "endLat": lat + half,
                "endLng": lng + half,
            }
            try:
                data = await self._connector._fetch_via_http(COMPLEX_SEARCH, params)
                cell_list = self._extract_complex_list(data)
                for c in cell_list:
                    kb_id = self._extract_kb_id(c)
                    if kb_id and kb_id not in seen_kb_ids:
                        seen_kb_ids.add(kb_id)
                        all_complexes.append(c)
                success_dongs += 1
            except (NetworkError, BrowserError, Exception) as e:
                logger.warning(f"법정동 박스 호출 실패 {d.get('법정동명')} ({region_code}): {e}")

        logger.info(
            f"Discovery {region_code}: dong {success_dongs}/{len(dong_list)}, "
            f"{len(all_complexes)} unique complexes"
        )

        if all_complexes:
            return all_complexes

        logger.warning(f"All dong-based calls returned 0 for {region_code}, browser fallback")
        return await self._fetch_complex_list_via_browser(region_code)

    @staticmethod
    def _sido_name_for(region_code: str) -> str:
        """region_code 앞 2자리로 KB 가 받는 시도명을 반환."""
        sido_map = {
            "11": "서울시",
            "26": "부산시",
            "27": "대구시",
            "28": "인천시",
            "29": "광주시",
            "30": "대전시",
            "31": "울산시",
            "36": "세종시",
            "41": "경기도",
            "42": "강원도",
            "43": "충청북도",
            "44": "충청남도",
            "45": "전라북도",
            "46": "전라남도",
            "47": "경상북도",
            "48": "경상남도",
            "50": "제주도",
            "51": "강원도",
            "52": "전라북도",
        }
        return sido_map.get(region_code[:2], "서울시")

    async def _fetch_complex_list_via_browser(self, region_code: str) -> List[dict]:
        """브라우저로 단지 목록 탐색"""
        session = await BrowserSessionManager.get_instance()
        page = await session.new_page()
        complexes = []

        try:
            # 응답 인터셉트
            async def handle_response(response):
                url = response.url
                if any(k in url.lower() for k in ["complex", "hscm", "danji"]):
                    try:
                        data = await response.json()
                        found = self._extract_complex_list(data)
                        complexes.extend(found)
                    except Exception:
                        pass

            page.on("response", handle_response)

            # 지도 페이지 이동
            await page.goto("https://kbland.kr/map", wait_until="networkidle", timeout=30000)
            await asyncio.sleep(get_random_delay(2.0, 4.0))

            # 검색 시도 (지역코드 또는 지역명으로 검색)
            search_selectors = [
                'input[placeholder*="검색"]',
                'input[placeholder*="단지"]',
                'input[type="search"]',
                ".search-input",
                "#searchInput",
            ]
            for selector in search_selectors:
                try:
                    el = page.locator(selector).first
                    if await el.is_visible(timeout=3000):
                        await el.click()
                        await el.fill(region_code)
                        await page.keyboard.press("Enter")
                        await asyncio.sleep(get_random_delay(3.0, 5.0))
                        break
                except Exception:
                    continue

            return complexes

        finally:
            await page.close()

    def _extract_complex_list(self, data: Any) -> List[dict]:
        """응답에서 단지 목록 추출"""
        if not isinstance(data, dict):
            return []

        # 다양한 응답 구조 대응
        for path in [
            ["dataBody", "data", "단지리스트"],
            ["dataBody", "data", "complexList"],
            ["dataBody", "data", "list"],
            ["data", "단지리스트"],
            ["data", "complexList"],
            ["data", "list"],
            ["단지리스트"],
            ["complexList"],
            ["list"],
            ["items"],
        ]:
            result = data
            for key in path:
                if isinstance(result, dict) and key in result:
                    result = result[key]
                else:
                    result = None
                    break
            if isinstance(result, list) and len(result) > 0:
                return result

        return []

    @staticmethod
    def _extract_kb_id(raw: dict) -> Optional[str]:
        """원시 데이터에서 KB 단지 ID 추출"""
        for key in ["단지기본일련번호", "hscmNo", "complexNo", "kb_complex_id", "단지번호", "id"]:
            if key in raw and raw[key]:
                return str(raw[key])
        return None

    def _create_complex(self, raw: dict, region_code: str, kb_id: str) -> Optional[Complex]:
        """원시 데이터에서 Complex + Area 레코드 생성"""
        # 단지명
        name = None
        for key in ["단지명", "hscmNm", "complexName", "name", "danjiNm"]:
            if key in raw and raw[key]:
                name = str(raw[key])
                break
        if not name:
            name = f"Unknown_{kb_id}"

        # 주소
        address = ""
        for key in ["주소", "addrNm", "address", "addr", "roadAddr"]:
            if key in raw and raw[key]:
                address = str(raw[key])
                break

        complex_obj = Complex(
            name=name,
            address=address,
            region_code=region_code[:5] if len(region_code) >= 5 else region_code,
            kb_complex_id=kb_id,
            priority=PriorityLevel.NORMAL,
            is_active=True,
            collect_listings=True,
        )
        self.db.add(complex_obj)
        self.db.flush()  # ID 할당

        # 면적 정보 생성
        area_list = raw.get("areaList") or raw.get("areas") or raw.get("면적목록") or []
        for area_data in area_list:
            exclusive = None
            for key in ["excArea", "exclusive_m2", "전용면적", "exclusiveArea"]:
                if key in area_data and area_data[key]:
                    try:
                        exclusive = float(str(area_data[key]).replace(",", ""))
                    except (ValueError, TypeError):
                        pass
                    break

            if exclusive is None or exclusive <= 0:
                continue

            supply = None
            for key in ["supArea", "supply_m2", "공급면적", "supplyArea"]:
                if key in area_data and area_data[key]:
                    try:
                        supply = float(str(area_data[key]).replace(",", ""))
                    except (ValueError, TypeError):
                        pass
                    break

            pyeong = None
            for key in ["pyeong", "평형", "py"]:
                if key in area_data and area_data[key]:
                    try:
                        pyeong = float(str(area_data[key]).replace(",", ""))
                    except (ValueError, TypeError):
                        pass
                    break

            kb_area_code = None
            for key in ["areaNo", "kb_area_code", "면적코드", "areaCode"]:
                if key in area_data and area_data[key]:
                    kb_area_code = str(area_data[key])
                    break

            area = Area(
                complex_id=complex_obj.id,
                exclusive_m2=exclusive,
                supply_m2=supply,
                pyeong=pyeong,
                kb_area_code=kb_area_code,
            )
            self.db.add(area)

        logger.info(f"Registered new complex: {name} (KB ID: {kb_id})")
        return complex_obj
