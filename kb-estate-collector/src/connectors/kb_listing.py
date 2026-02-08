from typing import Any, Dict, List
from datetime import datetime
import logging
from src.connectors.base import BaseConnector

logger = logging.getLogger(__name__)


class KBListingConnector(BaseConnector):
    """
    KB 매물/호가 데이터 수집 커넥터
    
    주의: 이것은 MOCK 구현입니다.
    실제 KB 사이트 접근은 법적 권한 확보 후 구현해야 합니다.
    """

    def __init__(self, rate_limit_per_minute: int = 30):
        super().__init__(
            name="KBListingConnector",
            rate_limit_per_minute=rate_limit_per_minute,
        )

    def fetch(self, complex_id: int, **kwargs) -> Dict[str, Any]:
        """
        MOCK: KB 매물 데이터 가져오기
        
        실제 구현 시:
        - 개인정보/연락처 수집 금지
        - 공개된 호가 정보만 수집
        - 법적 권한 확보 필수
        """
        logger.warning(
            f"MOCK fetch for complex_id={complex_id}. "
            "Real implementation required with legal compliance."
        )
        
        # Mock listings
        mock_listings = [
            {
                "listing_id": f"KB{complex_id}001",
                "ask_price": 510000000,
                "exclusive_m2": 84.5,
                "floor": 10,
                "status": "active",
                "posted_at": datetime.utcnow().isoformat(),
            },
            {
                "listing_id": f"KB{complex_id}002",
                "ask_price": 495000000,
                "exclusive_m2": 84.5,
                "floor": 5,
                "status": "active",
                "posted_at": datetime.utcnow().isoformat(),
            }
        ]
        
        return {
            "data": mock_listings,
            "metadata": {
                "source": "kb_mock",
                "fetched_at": datetime.utcnow().isoformat(),
                "count": len(mock_listings),
            }
        }

    def parse(self, raw_data: Any) -> List[Dict[str, Any]]:
        """Parse KB 매물 데이터 (개인정보 필터링)"""
        parsed_items = []
        
        for item in raw_data:
            # 개인정보 제거/필터링 로직이 여기에 들어가야 함
            parsed_items.append({
                "source_listing_id": item["listing_id"],
                "ask_price": item["ask_price"],
                "exclusive_m2": item.get("exclusive_m2"),
                "floor": item.get("floor"),
                "status": item.get("status", "active"),
                "posted_at": item.get("posted_at"),
                "source": "kb",
            })
        
        return parsed_items
