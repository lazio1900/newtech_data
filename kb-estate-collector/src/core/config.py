from typing import Optional

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application configuration settings"""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
    )

    # Database
    database_url: str = "postgresql://kb_user:kb_password@localhost:5432/kb_estate"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_key: str = "dev-api-key"

    # Celery
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "redis://localhost:6379/0"

    # Object Storage (Optional)
    s3_endpoint: Optional[str] = None
    s3_access_key: Optional[str] = None
    s3_secret_key: Optional[str] = None
    s3_bucket: str = "kb-estate-raw-data"

    # Logging
    log_level: str = "INFO"
    log_format: str = "json"

    # Rate Limiting
    default_rate_limit_per_minute: int = 60
    kb_rate_limit_per_minute: int = 20
    # 전역 KB 호출률 상한(분당). 모든 워커에 걸친 Redis 토큰버킷 ceiling — 현재 관측
    # throughput(~90-120/min)을 넘기는 보수적 기본값이라 평소엔 거의 안 걸리고 동시성을
    # 올렸을 때의 버스트만 막는다. KB 차단이 보이면 낮춘다.
    kb_global_rate_limit_per_minute: int = 150
    molit_rate_limit_per_minute: int = 60

    # 국토교통부 실거래가 OpenAPI
    molit_api_key: Optional[str] = None

    # Browser / Crawling
    browser_headless: bool = True
    browser_timeout_ms: int = 30000
    min_request_delay: float = 2.0
    max_request_delay: float = 5.0

    # KB 매물 인증 — 자동 로그인 (KB 자체 계정)
    kb_login_id: Optional[str] = None
    kb_login_password: Optional[str] = None
    # KB 매물 인증 fallback — 호스트 크롬에서 로그인 후 추출한 세션 쿠키
    kb_access_token: Optional[str] = None
    kb_refresh_token: Optional[str] = None

    # Notification
    slack_webhook_url: Optional[str] = None
    sentry_dsn: Optional[str] = None


settings = Settings()
