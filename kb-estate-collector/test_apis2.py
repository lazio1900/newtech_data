"""Test KB listing and transaction APIs - round 2."""
import httpx
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

BASE = 'https://api.kbland.kr'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Content-Type': 'application/json',
    'Referer': 'https://kbland.kr/',
    'Origin': 'https://kbland.kr',
    'webservice': '1',
}


def build_listing_params(lat, lng, region_code="", zoom=18, offset=0.002, select_code="1,2,3"):
    return {
        "selectCode": select_code,
        "zoomLevel": zoom,
        "startLat": lat - offset,
        "startLng": lng - offset,
        "endLat": lat + offset,
        "endLng": lng + offset,
        "물건종류": "01,05,41",
        "거래유형": "1,2,3",
        "매매시작값": "", "매매종료값": "",
        "보증금시작값": "", "보증금종료값": "",
        "월세시작값": "", "월세종료값": "",
        "면적시작값": "", "면적종료값": "",
        "준공년도시작값": "", "준공년도종료값": "",
        "방수": "", "욕실수": "",
        "세대수시작값": "", "세대수종료값": "",
        "관리비시작값": "", "관리비종료값": "",
        "용적률시작값": "", "용적률종료값": "",
        "건폐율시작값": "", "건폐율종료값": "",
        "전세가율시작값": "", "전세가율종료값": "",
        "매매전세차시작값": "", "매매전세차종료값": "",
        "월세수익률시작값": "", "월세수익률종료값": "",
        "구조": "", "주차": "", "엘리베이터": "", "보안옵션": "",
        "매물": "", "융자금": "",
        "분양단지구분코드": "C01",
        "일반분양여부": "1,0",
        "분양진행단계코드": "S01,S11,S12",
        "옵션": "",
        "점포수시작값": "", "점포수종료값": "",
        "지상층": "", "지하층": "", "지목": "", "용도지역": "", "추진현황": "",
        "webCheck": "Y",
        "법정동코드": region_code,
    }

lat, lng = 37.4938690, 127.0509446
region_code = "1168011800"

# Test 1: stutCdFilter with selectCode=2 (매물 only)
print("=== stutCdFilter selectCode=2 ===")
body = build_listing_params(lat, lng, region_code, select_code="2")
r = httpx.post(f'{BASE}/land-property/propList/stutCdFilter', headers=HEADERS, json=body, timeout=15.0)
resp = r.json()
rc = resp.get('dataBody', {}).get('resultCode')
data = resp.get('dataBody', {}).get('data')
print(f"rc={rc}")
if isinstance(data, dict):
    for k, v in data.items():
        if isinstance(v, list):
            print(f"  {k}: {len(v)} items")
            if v:
                print(f"  first: {json.dumps(v[0], ensure_ascii=False)[:500]}")
        else:
            print(f"  {k}: {str(v)[:200]}")
elif isinstance(data, list):
    print(f"  list: {len(data)} items")
    if data:
        print(f"  first: {json.dumps(data[0], ensure_ascii=False)[:500]}")
else:
    print(json.dumps(resp, ensure_ascii=False, indent=2)[:500])

# Test 2: stutCdFilter with 물건종류=01 only (apartment)
print("\n=== stutCdFilter 물건종류=01 only ===")
body2 = build_listing_params(lat, lng, region_code)
body2["물건종류"] = "01"
r2 = httpx.post(f'{BASE}/land-property/propList/stutCdFilter', headers=HEADERS, json=body2, timeout=15.0)
resp2 = r2.json()
rc2 = resp2.get('dataBody', {}).get('resultCode')
print(f"rc={rc2}")
data2 = resp2.get('dataBody', {}).get('data')
if isinstance(data2, (dict, list)):
    print(f"  type: {type(data2).__name__}")
    if isinstance(data2, dict):
        for k, v in data2.items():
            if isinstance(v, list):
                print(f"  {k}: {len(v)} items")
                if v:
                    print(f"  first: {json.dumps(v[0], ensure_ascii=False)[:500]}")
            else:
                print(f"  {k}: {str(v)[:200]}")
else:
    print(json.dumps(resp2, ensure_ascii=False, indent=2)[:500])

# Test 3: map250mBlwInfoList with selectCode=2 (includes listings?)
print("\n=== map250mBlwInfoList selectCode=2 ===")
body3 = build_listing_params(lat, lng, region_code, select_code="2")
r3 = httpx.post(f'{BASE}/land-complex/map/map250mBlwInfoList', headers=HEADERS, json=body3, timeout=15.0)
resp3 = r3.json()
data3 = resp3.get('dataBody', {}).get('data', {})
if isinstance(data3, dict):
    for k, v in data3.items():
        if isinstance(v, list):
            print(f"  {k}: {len(v)} items")
            if v:
                print(f"  first keys: {list(v[0].keys()) if isinstance(v[0], dict) else 'not dict'}")
                # Look for listing/property data
                sample = v[0] if isinstance(v[0], dict) else {}
                listing_keys = [key for key in sample.keys() if '매물' in key or '호가' in key or 'prop' in key.lower() or '매매' in key]
                if listing_keys:
                    print(f"  listing keys: {listing_keys}")
                    for lk in listing_keys:
                        print(f"    {lk}: {sample[lk]}")
        else:
            print(f"  {k}: {str(v)[:200]}")

# Test 4: listByBrhs with correct full params
print("\n=== listByBrhs ===")
body4 = {"단지기본일련번호": "13886"}
r4 = httpx.post(f'{BASE}/land-property/propList/listByBrhs', headers=HEADERS, json=body4, timeout=15.0)
resp4 = r4.json()
rc4 = resp4.get('dataBody', {}).get('resultCode')
data4 = resp4.get('dataBody', {}).get('data')
print(f"rc={rc4}")
if isinstance(data4, (dict, list)):
    if isinstance(data4, list):
        print(f"  {len(data4)} items")
        if data4:
            print(f"  first: {json.dumps(data4[0], ensure_ascii=False)[:500]}")
    elif isinstance(data4, dict):
        for k, v in data4.items():
            if isinstance(v, list):
                print(f"  {k}: {len(v)} items")
                if v:
                    print(f"  first: {json.dumps(v[0], ensure_ascii=False)[:500]}")
            else:
                print(f"  {k}: {str(v)[:200]}")
else:
    print(json.dumps(resp4, ensure_ascii=False, indent=2)[:500])

# Test 5: complexResteBrhs/infoByKey (per-complex property info)
print("\n=== complexResteBrhs/infoByKey ===")
r5 = httpx.get(
    f'{BASE}/land-complex/complexResteBrhs/infoByKey',
    headers={k: v for k, v in HEADERS.items() if k != 'Content-Type'},
    params={'단지기본일련번호': '13886'},
    timeout=15.0,
)
resp5 = r5.json()
rc5 = resp5.get('dataBody', {}).get('resultCode')
data5 = resp5.get('dataBody', {}).get('data')
print(f"rc={rc5}")
if isinstance(data5, dict):
    for k, v in data5.items():
        print(f"  {k}: {str(v)[:200]}")
elif isinstance(data5, list):
    print(f"  {len(data5)} items")
    if data5:
        print(f"  first: {json.dumps(data5[0], ensure_ascii=False)[:500]}")
else:
    print(json.dumps(resp5, ensure_ascii=False, indent=2)[:500])
