"""전체 단지 매물 일괄 수집 - 동기 httpx 직접 사용"""
import sys, time, math
sys.path.insert(0, ".")

import httpx
from datetime import datetime
from src.core.database import SessionLocal
from src.models.complex import Complex
from src.models.price_data import Listing, ListingStatus

HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/131.0.0.0 Safari/537.36",
    "Referer": "https://kbland.kr/",
    "Origin": "https://kbland.kr",
    "Accept": "application/json, text/plain, */*",
    "webservice": "1",
}
PAGE_SIZE = 50

STATUS_MAP = {"1": "active", "2": "active", "3": "sold", "4": "removed", "5": "removed"}


def fetch_listings(client, kb_id):
    """brif GET → propList/main POST → 전체 매물"""
    r1 = client.get(
        "https://api.kbland.kr/land-complex/complex/brif",
        params={"단지기본일련번호": kb_id},
    )
    if r1.status_code != 200:
        return []
    brif = r1.json().get("dataBody", {}).get("data", {})
    if not brif:
        return []

    total = (brif.get("매매건수") or 0) + (brif.get("전세건수") or 0) + (brif.get("월세건수") or 0)
    if total == 0:
        return []

    all_items = []
    max_pages = max(1, math.ceil(total / PAGE_SIZE))

    for page in range(1, max_pages + 1):
        body = {
            **brif,
            "페이지번호": page, "페이지목록수": PAGE_SIZE,
            "중복타입": "02", "정렬타입": "date",
            "매물거래구분": "", "면적일련번호": "",
            "전자계약여부": "0", "비대면대출여부": "0",
            "클린주택여부": "0", "honeyYn": "0",
        }
        r2 = client.post("https://api.kbland.kr/land-property/propList/main", json=body)
        if r2.status_code != 200:
            break
        data = r2.json().get("dataBody", {}).get("data", {})
        items = data.get("propertyList", [])
        if not items:
            break
        all_items.extend(items)
        srv_pages = data.get("페이지개수")
        if srv_pages and page >= int(srv_pages):
            break

    return all_items


def parse_listing(item):
    """단일 매물 파싱 (개인정보 제외)"""
    lid = item.get("매물일련번호")
    if not lid:
        return None

    price = None
    for k in ["매매가", "최소매매가", "전세가"]:
        v = item.get(k)
        if v is not None and v != "":
            try:
                price = int(str(v).replace(",", "")) * 10000
            except (ValueError, TypeError):
                continue
            if price:
                break
    if not price:
        return None

    m2 = None
    for k in ["순전용면적", "전용면적"]:
        v = item.get(k)
        if v is not None:
            try:
                m2 = float(str(v).replace(",", ""))
            except (ValueError, TypeError):
                pass
            if m2:
                break

    floor = None
    fs = item.get("해당층수", "")
    if fs:
        try:
            floor = int(str(fs).replace("층", "").replace(",", "").strip())
        except (ValueError, TypeError):
            pass

    status = STATUS_MAP.get(str(item.get("매물상태구분", "")), "active")
    reg = item.get("등록년월일", "")
    posted = reg.replace(".", "-") if "." in reg else None

    return {
        "lid": f"KB{lid}",
        "price": price,
        "m2": m2,
        "floor": floor,
        "status": status,
        "posted": posted,
    }


db = SessionLocal()
complexes = db.query(Complex).filter(
    Complex.is_active == True,
    Complex.kb_complex_id.isnot(None),
).all()

print(f"Total: {len(complexes)}", flush=True)

total_saved = 0
total_errors = 0
start = time.time()

with httpx.Client(headers=HEADERS, http2=True, timeout=30, follow_redirects=True) as client:
    for i, c in enumerate(complexes):
        try:
            time.sleep(2)  # rate limit
            raw_items = fetch_listings(client, c.kb_complex_id)

            saved = 0
            seen = set()
            for raw in raw_items:
                p = parse_listing(raw)
                if not p or p["lid"] in seen:
                    continue
                seen.add(p["lid"])

                existing = db.query(Listing).filter(Listing.source_listing_id == p["lid"]).first()
                if existing:
                    existing.ask_price = p["price"]
                    existing.status = ListingStatus.ACTIVE
                    existing.fetched_at = datetime.utcnow()
                    existing.last_seen_at = datetime.utcnow()
                else:
                    db.add(Listing(
                        complex_id=c.id,
                        source_listing_id=p["lid"],
                        ask_price=p["price"],
                        exclusive_m2=p["m2"],
                        floor=p["floor"],
                        status=ListingStatus.ACTIVE,
                        posted_at=p["posted"],
                        source="kb",
                        fetched_at=datetime.utcnow(),
                        last_seen_at=datetime.utcnow(),
                    ))
                saved += 1

            db.commit()
            total_saved += saved

            if (i + 1) % 20 == 0:
                elapsed = time.time() - start
                rate = (i + 1) / (elapsed / 60)
                print(f"  [{i+1}/{len(complexes)}] saved={total_saved} errors={total_errors} rate={rate:.0f}/min", flush=True)

        except Exception as e:
            db.rollback()
            total_errors += 1
            if total_errors <= 10:
                print(f"  Error {c.name}: {type(e).__name__}: {str(e)[:100]}", flush=True)

elapsed = time.time() - start
print(f"\nDone in {elapsed:.0f}s: saved={total_saved}, errors={total_errors}", flush=True)

total_db = db.query(Listing).count()
print(f"Total listings in DB: {total_db}", flush=True)
db.close()
