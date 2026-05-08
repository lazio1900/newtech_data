"""시각 처리 유틸 — 전 시스템 KST 기준."""
from __future__ import annotations

from datetime import datetime, timezone, timedelta

KST = timezone(timedelta(hours=9))


def now_kst() -> datetime:
    """현재 시각을 naive KST datetime 으로 반환.

    DB 컬럼은 TIMESTAMP WITHOUT TIMEZONE 이므로 tzinfo 를 떼서 저장.
    한국 단일 서비스이므로 일관성 위해 KST 고정.
    """
    return datetime.now(KST).replace(tzinfo=None)
