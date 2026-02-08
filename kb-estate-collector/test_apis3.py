"""Test KB price chart and historical data endpoints."""
import httpx
import json
import sys

sys.stdout.reconfigure(encoding='utf-8')

BASE = 'https://api.kbland.kr'
HEADERS = {
    'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36',
    'Accept': 'application/json, text/plain, */*',
    'Referer': 'https://kbland.kr/',
    'Origin': 'https://kbland.kr',
    'webservice': '1',
}

kb_id = '13886'
area_id = '13663'

# Test 1: IntgrationChart (integrated price chart - may have tx data)
print("=== PerMn/IntgrationChart ===")
r1 = httpx.get(
    f'{BASE}/land-price/price/PerMn/IntgrationChart',
    headers=HEADERS,
    params={'단지기본일련번호': kb_id, '면적일련번호': area_id, '거래유형': '1'},
    timeout=15.0,
)
resp1 = r1.json()
data1 = resp1.get('dataBody', {}).get('data')
rc1 = resp1.get('dataBody', {}).get('resultCode')
print(f"rc={rc1}")
if isinstance(data1, dict):
    for k, v in data1.items():
        if isinstance(v, list):
            print(f"  {k}: {len(v)} items")
            if v:
                print(f"  first: {json.dumps(v[0], ensure_ascii=False)[:300]}")
                if len(v) > 1:
                    print(f"  last: {json.dumps(v[-1], ensure_ascii=False)[:300]}")
        else:
            print(f"  {k}: {str(v)[:200]}")
elif isinstance(data1, list):
    print(f"  {len(data1)} items")
    if data1:
        print(f"  first: {json.dumps(data1[0], ensure_ascii=False)[:300]}")
else:
    print(json.dumps(resp1, ensure_ascii=False, indent=2)[:1000])

# Test 2: frcsPriceInq (forecast price)
print("\n=== frcsPriceInq ===")
r2 = httpx.get(
    f'{BASE}/land-price/price/frcsPriceInq',
    headers=HEADERS,
    params={'단지기본일련번호': kb_id, '면적일련번호': area_id},
    timeout=15.0,
)
print(json.dumps(r2.json(), ensure_ascii=False, indent=2)[:1000])

# Test 3: QuotBaseYear (quote base year - historical prices)
print("\n=== QuotBaseYear ===")
r3 = httpx.get(
    f'{BASE}/land-price/price/QuotBaseYear',
    headers=HEADERS,
    params={'단지기본일련번호': kb_id, '면적일련번호': area_id},
    timeout=15.0,
)
resp3 = r3.json()
data3 = resp3.get('dataBody', {}).get('data')
rc3 = resp3.get('dataBody', {}).get('resultCode')
print(f"rc={rc3}")
if isinstance(data3, (dict, list)):
    if isinstance(data3, dict):
        for k, v in data3.items():
            if isinstance(v, list) and v:
                print(f"  {k}: {len(v)} items, first={json.dumps(v[0], ensure_ascii=False)[:300]}")
            elif isinstance(v, str):
                print(f"  {k}: {v[:200]}")
            else:
                print(f"  {k}: {v}")
    elif isinstance(data3, list) and data3:
        print(f"  {len(data3)} items, first={json.dumps(data3[0], ensure_ascii=False)[:300]}")
else:
    print(json.dumps(resp3, ensure_ascii=False, indent=2)[:500])

# Test 4: SmlrSqrmsr/QuotLncrdcRate (similar size price rate)
print("\n=== SmlrSqrmsr/QuotLncrdcRate ===")
r4 = httpx.get(
    f'{BASE}/land-price/price/SmlrSqrmsr/QuotLncrdcRate',
    headers=HEADERS,
    params={'단지기본일련번호': kb_id, '면적일련번호': area_id},
    timeout=15.0,
)
resp4 = r4.json()
data4 = resp4.get('dataBody', {}).get('data')
rc4 = resp4.get('dataBody', {}).get('resultCode')
print(f"rc={rc4}")
if isinstance(data4, dict):
    for k, v in data4.items():
        if isinstance(v, list) and v:
            print(f"  {k}: {len(v)} items, first={json.dumps(v[0], ensure_ascii=False)[:300]}")
        else:
            print(f"  {k}: {str(v)[:200]}")
elif isinstance(data4, list) and data4:
    print(f"  {len(data4)} items, first={json.dumps(data4[0], ensure_ascii=False)[:300]}")
else:
    print(json.dumps(resp4, ensure_ascii=False, indent=2)[:500])

# Test 5: vlaDealDtailPriceInq with webservice header (another try)
print("\n=== vlaDealDtailPriceInq with webservice:1 ===")
r5 = httpx.get(
    f'{BASE}/land-complex/vlaHscmDtail/vlaDealDtailPriceInq',
    headers=HEADERS,
    params={'단지기본일련번호': kb_id, '면적일련번호': area_id, '거래유형': '1'},
    timeout=15.0,
)
print(json.dumps(r5.json(), ensure_ascii=False, indent=2)[:1000])

# Test 6: vlaPastDealPriceInqByYear with year parameter
print("\n=== vlaPastDealPriceInqByYear with year ===")
r6 = httpx.get(
    f'{BASE}/land-complex/vlaHscmDtail/vlaPastDealPriceInqByYear',
    headers=HEADERS,
    params={'단지기본일련번호': kb_id, '면적일련번호': area_id, '거래유형': '1', '조회년도': '2025'},
    timeout=15.0,
)
print(json.dumps(r6.json(), ensure_ascii=False, indent=2)[:1000])

# Test 7: vlaRealPriceInq
print("\n=== vlaRealPriceInq ===")
r7 = httpx.get(
    f'{BASE}/land-complex/vlaHscmDtail/vlaRealPriceInq',
    headers=HEADERS,
    params={'단지기본일련번호': kb_id, '면적일련번호': area_id},
    timeout=15.0,
)
print(json.dumps(r7.json(), ensure_ascii=False, indent=2)[:2000])
