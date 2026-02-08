"""Test KB APIs with correct parameters."""
import httpx
import json
import sys

BASE = 'https://api.kbland.kr'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Content-Type': 'application/json',
    'Referer': 'https://kbland.kr/',
    'Origin': 'https://kbland.kr',
    'webservice': '1',
}


def build_listing_params(lat: float, lng: float, region_code: str = "", zoom: int = 18, offset: float = 0.002):
    """Build the full 53-parameter body for stutCdFilter."""
    return {
        "selectCode": "1,2,3",
        "zoomLevel": zoom,
        "startLat": lat - offset,
        "startLng": lng - offset,
        "endLat": lat + offset,
        "endLng": lng + offset,
        "물건종류": "01,05,41",
        "거래유형": "1,2,3",
        "매매시작값": "",
        "매매종료값": "",
        "보증금시작값": "",
        "보증금종료값": "",
        "월세시작값": "",
        "월세종료값": "",
        "면적시작값": "",
        "면적종료값": "",
        "준공년도시작값": "",
        "준공년도종료값": "",
        "방수": "",
        "욕실수": "",
        "세대수시작값": "",
        "세대수종료값": "",
        "관리비시작값": "",
        "관리비종료값": "",
        "용적률시작값": "",
        "용적률종료값": "",
        "건폐율시작값": "",
        "건폐율종료값": "",
        "전세가율시작값": "",
        "전세가율종료값": "",
        "매매전세차시작값": "",
        "매매전세차종료값": "",
        "월세수익률시작값": "",
        "월세수익률종료값": "",
        "구조": "",
        "주차": "",
        "엘리베이터": "",
        "보안옵션": "",
        "매물": "",
        "융자금": "",
        "분양단지구분코드": "C01",
        "일반분양여부": "1,0",
        "분양진행단계코드": "S01,S11,S12",
        "옵션": "",
        "점포수시작값": "",
        "점포수종료값": "",
        "지상층": "",
        "지하층": "",
        "지목": "",
        "용도지역": "",
        "추진현황": "",
        "webCheck": "Y",
        "법정동코드": region_code,
    }


def test_listing_count(lat, lng, region_code=""):
    body = build_listing_params(lat, lng, region_code)
    r = httpx.post(f'{BASE}/land-property/propList/stutCdFilter/count', headers=HEADERS, json=body, timeout=15.0)
    return r.json()


def test_listing(lat, lng, region_code=""):
    body = build_listing_params(lat, lng, region_code)
    r = httpx.post(f'{BASE}/land-property/propList/stutCdFilter', headers=HEADERS, json=body, timeout=15.0)
    return r.json()


def test_listing_by_brhs(kb_complex_id):
    body = build_listing_params(0, 0)  # start with listing params
    body['단지기본일련번호'] = kb_complex_id
    r = httpx.post(f'{BASE}/land-property/propList/listByBrhs', headers=HEADERS, json=body, timeout=15.0)
    return r.json()


def test_transaction(kb_complex_id, area_id):
    r = httpx.get(
        f'{BASE}/land-complex/vlaHscmDtail/vlaDealDtailPriceInq',
        headers={k: v for k, v in HEADERS.items() if k != 'Content-Type'},
        params={'단지기본일련번호': kb_complex_id, '면적일련번호': area_id, '거래유형': '1'},
        timeout=15.0,
    )
    return r.json()


if __name__ == '__main__':
    # 은마아파트 coords and region code
    lat, lng = 37.4938690, 127.0509446
    region_code = "1168011800"  # 대치동
    kb_id = '13886'
    area_id = '13663'

    sys.stdout.reconfigure(encoding='utf-8')

    print("=== Listing Count ===")
    result = test_listing_count(lat, lng, region_code)
    print(json.dumps(result, ensure_ascii=False, indent=2))

    print("\n=== Listing Data ===")
    result2 = test_listing(lat, lng, region_code)
    data = result2.get('dataBody', {}).get('data')
    rc = result2.get('dataBody', {}).get('resultCode')
    print(f"resultCode: {rc}")
    if isinstance(data, dict):
        for k, v in data.items():
            if isinstance(v, list):
                print(f"  {k}: {len(v)} items")
                if v:
                    print(f"  first: {json.dumps(v[0], ensure_ascii=False)[:500]}")
            else:
                print(f"  {k}: {str(v)[:200]}")
    else:
        print(json.dumps(result2, ensure_ascii=False, indent=2)[:1000])

    print("\n=== Transaction ===")
    result3 = test_transaction(kb_id, area_id)
    print(json.dumps(result3, ensure_ascii=False, indent=2)[:2000])
