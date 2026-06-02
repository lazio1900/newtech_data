"""전역 Redis 토큰버킷 레이트리밋.

기존 BaseConnector._wait_for_rate_limit 은 인스턴스 변수(last_request_time)에 의존하는데
leaf task 마다 새 커넥터를 만들어 매번 리셋되므로 전역 throttle 이 사실상 없었다.
이 토큰버킷은 Redis 에 상태를 둬 모든 워커 프로세스에 걸친 전역 호출률 상한을 강제한다.

reserve-and-wait 방식: 호출 시 토큰 1개를 예약하고 부족분만큼 대기(초)를 돌려준다.
토큰을 음수까지 허용(대기열)해 동시 호출이 자연히 rate 로 직렬화된다. 실패하면 fail-open.
"""

import logging
import time
from typing import Dict, Optional

import redis

from src.core.config import settings

logger = logging.getLogger(__name__)

_LUA = """
local bucket = KEYS[1]
local rate = tonumber(ARGV[1])
local burst = tonumber(ARGV[2])
local need = tonumber(ARGV[3])
local t = redis.call('TIME')
local now = tonumber(t[1]) + tonumber(t[2]) / 1000000.0
local data = redis.call('HMGET', bucket, 'tokens', 'ts')
local tokens = tonumber(data[1])
local ts = tonumber(data[2])
if tokens == nil then tokens = burst; ts = now end
tokens = math.min(burst, tokens + math.max(0, now - ts) * rate)
tokens = tokens - need
local wait = 0.0
if tokens < 0 then wait = -tokens / rate end
redis.call('HMSET', bucket, 'tokens', tokens, 'ts', now)
redis.call('PEXPIRE', bucket, math.ceil(burst / rate * 1000) + 5000)
return tostring(wait)
"""

_buckets: Dict[str, "RedisTokenBucket"] = {}


class RedisTokenBucket:
    def __init__(self, key: str, rate_per_minute: int, burst: Optional[int] = None):
        self.key = f"ratelimit:{key}"
        self.rate = max(rate_per_minute, 1) / 60.0
        self.burst = burst if burst is not None else max(2, rate_per_minute // 6)
        self._client = redis.from_url(settings.celery_broker_url)
        self._script = self._client.register_script(_LUA)

    def acquire(self, tokens: int = 1, max_wait: float = 120.0) -> None:
        try:
            wait = float(self._script(keys=[self.key], args=[self.rate, self.burst, tokens]))
        except Exception as e:
            logger.warning(f"token bucket {self.key} failed open: {e}")
            return
        if wait > 0:
            time.sleep(min(wait, max_wait))


def get_bucket(key: str, rate_per_minute: int) -> RedisTokenBucket:
    """프로세스 내 버킷 캐시 (redis client/script 재사용). 상태는 Redis 에서 전역 공유."""
    b = _buckets.get(key)
    if b is None:
        b = RedisTokenBucket(key, rate_per_minute)
        _buckets[key] = b
    return b
