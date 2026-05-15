"""
KB 매물/호가 데이터 수집 커넥터.

KB부동산에서 아파트 단지별 매물 정보를 수집합니다.
개인정보(연락처 등)는 수집하지 않습니다.

API 흐름:
1. GET /land-complex/complex/brif?단지기본일련번호={id} → 단지 브리프
2. POST /land-property/propList/main (body: brif + 페이지 파라미터) → 매물 목록
"""
import asyncio
import concurrent.futures
import logging
import math
from typing import Any, Callable, Dict, List, Optional, Tuple

import httpx

from src.connectors.base import NetworkError, ParserError
from src.connectors.kb_base import KBBaseConnector
from src.connectors.kb_endpoints import COMPLEX_BRIF, COMPLEX_PROP_LIST, KBEndpoint

logger = logging.getLogger(__name__)

# 매물 상태 매핑 (KB 매물상태구분 → 내부 상태)
STATUS_MAP = {
    "1": "active",  # 등록대기
    "2": "active",  # 등록중
    "3": "sold",  # 거래완료
    "4": "removed",  # 삭제
    "5": "removed",  # 기간만료
}

PAGE_SIZE = 50  # 한 페이지에 요청할 매물 수 (최대 50)

# 거래유형 코드 매핑 (KB land URL 의 매물거래구분 값 → 내부 trade_type)
TRADE_CODE_NAME = {"1": "매매", "2": "전세", "3": "월세"}


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
        """propList/main은 2단계 API이므로 여기선 brif 엔드포인트만 반환."""
        kb_complex_id = kwargs.get("kb_complex_id") or self._resolve_kb_complex_id(
            kwargs["complex_id"]
        )
        return (COMPLEX_BRIF, {"단지기본일련번호": kb_complex_id})

    def _build_browser_config(self, **kwargs) -> Tuple[str, str, Optional[Callable]]:
        """매물 브라우저 폴백 설정. trade_code(1=매매/2=전세/3=월세) 에 따라 페이지 query 분기."""
        kb_complex_id = kwargs.get("kb_complex_id") or self._resolve_kb_complex_id(
            kwargs["complex_id"]
        )
        trade_code = str(kwargs.get("trade_code") or "1")
        # 매물종별구분=01 (아파트), 매물거래구분=1/2/3
        page_url = (
            f"https://kbland.kr/pl/{kb_complex_id}"
            f"?%EB%A7%A4%EB%AC%BC%EC%A2%85%EB%B3%84%EA%B5%AC%EB%B6%84=01"
            f"&%EB%A7%A4%EB%AC%BC%EA%B1%B0%EB%9E%98%EA%B5%AC%EB%B6%84={trade_code}"
        )
        api_pattern = "propList/main"
        return (page_url, api_pattern, None)

    # Transient 오류 — 재시도 가능
    _TRANSIENT_EXC = (
        httpx.RemoteProtocolError,
        httpx.ReadTimeout,
        httpx.ConnectTimeout,
        httpx.ConnectError,
        httpx.WriteError,
        httpx.PoolTimeout,
    )

    def _request_with_retry(
        self, client: "httpx.Client", method: str, url: str, *, max_retries: int = 5, **kwargs
    ) -> "httpx.Response":
        """transient 네트워크 오류(서버 disconnect, timeout 등)는 지수백오프로 재시도.
        KB propList/main 이 자주 끊겨 backoff 를 길게 (총 ~30초까지)."""
        import time as _time

        last_exc = None
        for attempt in range(1, max_retries + 1):
            try:
                if method == "GET":
                    return client.get(url, **kwargs)
                if method == "POST":
                    return client.post(url, **kwargs)
                raise ValueError(f"unsupported method {method}")
            except self._TRANSIENT_EXC as e:
                last_exc = e
                if attempt == max_retries:
                    break
                wait = min(1.0 * (2 ** (attempt - 1)), 15.0)  # 1, 2, 4, 8, 15
                logger.warning(
                    f"{self.name}: {method} {url} transient error '{e}', retry {attempt}/{max_retries} in {wait}s"
                )
                _time.sleep(wait)
        raise NetworkError(f"transient request failed after {max_retries} attempts: {last_exc}")

    def fetch(self, **kwargs) -> Dict[str, Any]:
        """동기 2단계 fetch: brif GET → propList/main POST (trade_code 별 전체 페이지 순회).
        trade_code (1=매매/2=전세/3=월세) 매개변수로 거래유형별 호출 분리."""
        kb_complex_id = kwargs.get("kb_complex_id") or self._resolve_kb_complex_id(
            kwargs["complex_id"]
        )
        trade_code = str(kwargs.get("trade_code") or "1")
        count_field = {"1": "매매건수", "2": "전세건수", "3": "월세건수"}[trade_code]

        with httpx.Client(
            headers=self._get_default_headers(),
            http2=False,
            timeout=30.0,
            follow_redirects=True,
        ) as client:
            # Step 1: GET brif
            logger.info(f"{self.name}: GET brif for complex {kb_complex_id} (trade={trade_code})")
            brif_resp = self._request_with_retry(
                client,
                "GET",
                COMPLEX_BRIF.url,
                params={"단지기본일련번호": kb_complex_id},
            )
            if brif_resp.status_code != 200:
                raise NetworkError(f"brif HTTP {brif_resp.status_code}")
            brif_data = brif_resp.json().get("dataBody", {}).get("data", {})
            if not brif_data:
                raise NetworkError(f"brif returned empty data for {kb_complex_id}")

            trade_count = brif_data.get(count_field) or 0
            logger.info(
                f"{self.name}: {brif_data.get('단지명')} trade={trade_code} count={trade_count}"
            )

            if trade_count == 0:
                return {
                    "data": {"propertyList": []},
                    "metadata": {"method": "http_direct", "source": "kb", "trade_code": trade_code},
                }

            # Step 2: POST propList/main — 해당 trade_code 만 (KB 가 매물거래구분 필터 지원)
            all_items = []
            total_pages = max(1, math.ceil(trade_count / PAGE_SIZE))

            for page_no in range(1, total_pages + 1):
                post_body = {
                    **brif_data,
                    "페이지번호": page_no,
                    "페이지목록수": PAGE_SIZE,
                    "중복타입": "02",
                    "정렬타입": "date",
                    "매물거래구분": trade_code,
                    "면적일련번호": "",
                    "전자계약여부": "0",
                    "비대면대출여부": "0",
                    "클린주택여부": "0",
                    "honeyYn": "0",
                }

                try:
                    prop_resp = self._request_with_retry(
                        client,
                        "POST",
                        COMPLEX_PROP_LIST.url,
                        json=post_body,
                    )
                except NetworkError as e:
                    logger.warning(f"{self.name}: propList page {page_no} retry exhausted: {e}")
                    break
                if prop_resp.status_code != 200:
                    logger.warning(
                        f"{self.name}: propList page {page_no} HTTP {prop_resp.status_code}"
                    )
                    break

                prop_data = prop_resp.json().get("dataBody", {}).get("data", {})
                items = prop_data.get("propertyList", [])
                if not items:
                    break

                all_items.extend(items)

                # 서버가 알려주는 실제 총 페이지수 반영
                server_pages = prop_data.get("페이지개수")
                if server_pages and page_no >= int(server_pages):
                    break

        method = "http_direct"
        if not all_items and trade_count > 0:
            logger.info(f"{self.name}: HTTP propList exhausted, falling back to browser")
            browser_items = self._fetch_via_browser_sync(**kwargs)
            if browser_items:
                all_items.extend(browser_items)
                method = "browser_intercept"

        logger.info(
            f"{self.name}: Fetched {len(all_items)} listings for "
            f"{brif_data.get('단지명')} (trade={trade_code})"
        )
        return {
            "data": {"propertyList": all_items, "총매물건수": len(all_items)},
            "metadata": {"method": method, "source": "kb", "trade_code": trade_code},
        }

    async def _ensure_logged_in(self):
        # KB land 인증 확보. 우선순위: 기존 쿠키 > 자동 로그인 (ID/PW) > env 토큰 fallback.
        from src.browser.session_manager import BrowserSessionManager
        from src.core.config import settings

        session = await BrowserSessionManager.get_instance()
        ctx = session._context
        cookies = await ctx.cookies("https://kbland.kr")
        if any(c["name"] == "accessToken_" for c in cookies):
            return

        if settings.kb_login_id and settings.kb_login_password:
            try:
                await self._do_kb_auto_login(ctx, settings)
                return
            except Exception as e:
                logger.warning(f"{self.name}: KB auto-login failed ({e})")

        if settings.kb_access_token and settings.kb_refresh_token:
            await ctx.add_cookies(
                [
                    {
                        "name": "accessToken_",
                        "value": settings.kb_access_token,
                        "domain": ".kbland.kr",
                        "path": "/",
                    },
                    {
                        "name": "refreshToken_",
                        "value": settings.kb_refresh_token,
                        "domain": ".kbland.kr",
                        "path": "/",
                    },
                ]
            )
            logger.info(f"{self.name}: KB session cookies injected from env (fallback)")
            return

        logger.warning(f"{self.name}: no KB auth available; propList/main will fail")

    async def _do_kb_auto_login(self, ctx, settings):
        # 좌측 GNB "메뉴" → "로그인해보세요" → "휴대폰 또는 이메일 로그인" → 폼 fill → Enter.
        logger.info(f"{self.name}: KB auto-login starting")
        page = await ctx.new_page()
        try:
            await page.goto("https://kbland.kr", wait_until="networkidle", timeout=30000)
            await asyncio.sleep(2)
            await page.evaluate(
                "() => [...document.querySelectorAll('.btn-gnb')]"
                ".find(b => b.innerText.trim() === '메뉴').click()"
            )
            await asyncio.sleep(2)
            await page.evaluate(
                "() => [...document.querySelectorAll('button')]"
                ".find(b => b.innerText.trim().startsWith('로그인해보세요')).click()"
            )
            await asyncio.sleep(2)
            await page.evaluate(
                "() => { const b = [...document.querySelectorAll('button')]"
                ".find(b => b.innerText.trim() === '휴대폰 또는 이메일 로그인'"
                " && b.offsetParent !== null); if (b) b.click(); }"
            )
            await asyncio.sleep(3)
            await page.fill(
                'input[placeholder="휴대폰 번호 또는 이메일 입력"]', settings.kb_login_id
            )
            await page.fill('input[placeholder="비밀번호 입력"]', settings.kb_login_password)
            await page.press('input[placeholder="비밀번호 입력"]', "Enter")
            await asyncio.sleep(5)

            cookies = await ctx.cookies("https://kbland.kr")
            if not any(c["name"] == "accessToken_" for c in cookies):
                raise NetworkError("accessToken_ cookie not issued after login")
            logger.info(f"{self.name}: KB auto-login successful")
        finally:
            await page.close()

    def _fetch_via_browser_sync(self, **kwargs) -> List[dict]:
        # KB가 비로그인 httpx POST 를 disconnect 시킬 때 사용. Playwright 로 매물
        # 페이지 띄워 propList/main 응답을 인터셉트. 첫 페이지(최대 50건)만 가져옴.
        page_url, api_pattern, interaction = self._build_browser_config(**kwargs)

        async def _run():
            await self._ensure_logged_in()
            return await self._fetch_via_browser(page_url, api_pattern, interaction)

        try:
            loop = asyncio.get_event_loop()
            if loop.is_running():
                with concurrent.futures.ThreadPoolExecutor() as pool:
                    raw = pool.submit(asyncio.run, _run()).result()
            else:
                raw = loop.run_until_complete(_run())
        except RuntimeError:
            raw = asyncio.run(_run())

        data = (raw.get("dataBody") or {}).get("data") or {}
        return data.get("propertyList") or []

    def parse(self, raw_data: Any) -> List[Dict[str, Any]]:
        """
        KB 매물 응답 파싱.
        raw_data.metadata.trade_code 가 있으면 응답에 매물거래구분명 없는 매물의
        trade_type 보강에 사용한다.
        """
        try:
            fallback_trade_type = None
            if isinstance(raw_data, dict):
                meta = raw_data.get("metadata", {})
                if isinstance(meta, dict):
                    fallback_trade_type = TRADE_CODE_NAME.get(str(meta.get("trade_code") or ""))

            data = raw_data
            if isinstance(data, dict):
                data = data.get("dataBody", data)
                if isinstance(data, dict):
                    data = data.get("data", data)

            prop_list = []
            if isinstance(data, dict):
                prop_list = data.get("propertyList", [])
            elif isinstance(data, list):
                prop_list = data

            parsed = []
            seen_ids = set()
            for item in prop_list:
                if not isinstance(item, dict):
                    continue
                listing = self._parse_single_listing(item, fallback_trade_type)
                if listing and listing["source_listing_id"] not in seen_ids:
                    seen_ids.add(listing["source_listing_id"])
                    parsed.append(listing)

            return parsed

        except Exception as e:
            raise ParserError(f"Failed to parse KB listing data: {e}") from e

    def _parse_single_listing(
        self, item: dict, fallback_trade_type: Optional[str] = None
    ) -> Optional[Dict[str, Any]]:
        """단일 매물 항목 파싱 (개인정보 필터링 포함)"""
        # 매물 ID
        listing_id = item.get("매물일련번호")
        if not listing_id:
            return None
        listing_id = f"KB{listing_id}"

        # 거래유형 (가격 분기에 필요). 응답에 없으면 호출 측 trade_code 의 한글명으로 보강.
        trade_type = item.get("매물거래구분명") or fallback_trade_type

        # 호가 (만원 → 원) — 거래유형별로 분기. 매매에 전세가, 전세에 매매가 섞이지 않게.
        if trade_type == "매매":
            price_keys = ["매매가", "최소매매가"]
        elif trade_type == "전세":
            price_keys = ["전세가"]
        elif trade_type == "월세":
            price_keys = ["보증금"]
        else:
            price_keys = []

        ask_price = None
        for key in price_keys:
            val = item.get(key)
            if val is not None and val != "" and val != "null":
                ask_price = self._to_won(val)
                if ask_price:
                    break
        if not ask_price:
            return None

        # 전용면적 (순전용면적이 더 정확)
        exclusive_m2 = None
        for key in ["순전용면적", "전용면적"]:
            val = item.get(key)
            if val is not None:
                try:
                    exclusive_m2 = float(str(val).replace(",", "").strip())
                except (ValueError, TypeError):
                    pass
                if exclusive_m2:
                    break

        # 층
        floor = None
        floor_str = item.get("해당층수", "")
        if floor_str:
            try:
                floor = int(str(floor_str).replace("층", "").replace(",", "").strip())
            except (ValueError, TypeError):
                pass

        # 상태
        status_code = str(item.get("매물상태구분", ""))
        status = STATUS_MAP.get(status_code, "active")

        # 등록일
        posted_at = None
        reg_date = item.get("등록년월일", "")
        if reg_date:
            # "2026.02.07" format
            posted_at = (
                reg_date.replace(".", "-") if "." in reg_date else self._parse_date(reg_date)
            )

        return {
            "source_listing_id": listing_id,
            "ask_price": ask_price,
            "exclusive_m2": exclusive_m2,
            "floor": floor,
            "status": status,
            "posted_at": posted_at,
            "source": "kb",
            "trade_type": trade_type,
        }
