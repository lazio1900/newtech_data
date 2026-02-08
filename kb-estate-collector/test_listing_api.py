"""KBListingConnector 직접 테스트 - 동아불암(971)"""
import sys
sys.path.insert(0, ".")

from src.core.database import SessionLocal
from src.connectors.kb_listing import KBListingConnector

db = SessionLocal()

try:
    connector = KBListingConnector(db_session=db)
    # kb_complex_id를 직접 전달하여 DB 조회 건너뛰기
    result = connector.collect(kb_complex_id="971")

    print(f"Items: {len(result['items'])}")
    for i, item in enumerate(result['items'][:5]):
        print(f"  [{i+1}] {item['source_listing_id']}: "
              f"{item['ask_price']//10000}만원, "
              f"{item.get('exclusive_m2')}m2, "
              f"{item.get('floor')}층, "
              f"상태={item.get('status')}, "
              f"등록={item.get('posted_at')}")

    if len(result['items']) > 5:
        print(f"  ... ({len(result['items'])-5} more)")

    print(f"\nMetadata: {result.get('metadata', {}).get('method')}")
    print(f"Raw propertyList count: {len(result.get('raw', {}).get('propertyList', []))}")

except Exception as e:
    print(f"Error: {type(e).__name__}: {e}")
    import traceback
    traceback.print_exc()

finally:
    db.close()
