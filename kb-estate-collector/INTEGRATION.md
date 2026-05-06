# newtech_data ↔ newtech-platform 연동 가이드

## 역할

| 프로젝트 | 역할 | 경로 |
|----------|------|------|
| **newtech_data** (이 프로젝트) | 데이터 수집 (크롤링) | `/Users/lmj/00_projects/newtech_data/kb-estate-collector` |
| **newtech-platform** | 사용자 서비스 (대출심사 플랫폼) | `/Users/lmj/00_projects/newtech-platform` |

## 공유 인프라

두 프로젝트는 **하나의 PostgreSQL과 Redis**를 공유합니다.

| 서비스 | 포트 | 컨테이너 | DB/유저 |
|--------|------|----------|---------|
| PostgreSQL | **5433** | `newtech-platform` docker-compose에서 기동 | `kb_estate` / `kb_user` |
| Redis | **6379** | `newtech-platform` docker-compose에서 기동 | DB 0 |

> **중요**: 인프라(PostgreSQL, Redis)는 `newtech-platform`의 docker-compose로 통합 관리합니다.
> `newtech_data`의 docker-compose는 단독 개발/테스트 시에만 사용합니다.

## 포트 할당 (고정)

| 서비스 | 포트 | 프로젝트 |
|--------|------|----------|
| PostgreSQL | 5433 | 공유 |
| Redis | 6379 | 공유 |
| **newtech-platform** Backend (FastAPI) | **8002** | newtech-platform |
| **newtech-platform** Frontend | **5173** | newtech-platform |
| **newtech_data** Backend (FastAPI) | **8000** | newtech_data |
| **newtech_data** Frontend (Vite) | **5174** | newtech_data |
| Celery Worker | - (포트 없음) | newtech_data |

## DB 테이블 소유권

### newtech_data 소유 (Collector)
크롤링/수집 관련 테이블. newtech-platform은 **읽기 전용**으로 참조.

| 테이블 | 설명 |
|--------|------|
| `complexes` | 아파트 단지 (kb_complex_id, region_code 등) |
| `areas` | 단지별 면적 타입 (전용면적, 공급면적) |
| `crawl_jobs` | 수집 작업 정의 |
| `crawl_runs` | 수집 실행 이력 |
| `crawl_tasks` | 개별 수집 태스크 |
| `raw_payloads` | 원문 데이터 스냅샷 |
| `kb_prices` | KB 시세 데이터 |
| `transactions` | 실거래가 |
| `listings` | 매물 정보 |

### newtech-platform 소유 (App)
서비스 로직 테이블. newtech_data는 접근하지 않음.

| 테이블 | 설명 |
|--------|------|
| `users` | 사용자 계정 (CUSTOMER, AUDITOR, ADMIN) |
| `loan_applications` | 대출 심사 신청 |
| `monitoring_loans` | 실행 후 모니터링 |
| `search_history` | 검색 자동완성 |
| `analysis_audit_logs` | AI 분석 감사 로그 |

## 이 프로젝트(.env) 설정

```env
# 공유 인프라에 연결 (newtech-platform docker-compose 기준)
DATABASE_URL=postgresql://kb_user:kb_password@localhost:5433/kb_estate
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# 이 프로젝트 전용 포트
API_HOST=0.0.0.0
API_PORT=8000
```

## 기동 순서

```bash
# 1. 인프라 (newtech-platform에서 기동, 이미 실행 중이면 스킵)
cd /Users/lmj/00_projects/newtech-platform
docker-compose up -d postgres redis

# 2. newtech_data 백엔드
cd /Users/lmj/00_projects/newtech_data/kb-estate-collector
source .venv/bin/activate
uvicorn src.admin_api.main:app --host 0.0.0.0 --port 8000 --reload

# 3. newtech_data Celery Worker (별도 터미널)
celery -A src.workers.celery_app worker --loglevel=info --pool=solo

# 4. newtech_data 프론트엔드 (별도 터미널)
cd frontend && npm run dev
# → http://localhost:5174
```

## 단독 개발 시 (newtech-platform 없이)

newtech-platform이 실행되지 않은 상태에서 이 프로젝트만 테스트하려면:

```bash
# 이 프로젝트의 docker-compose 사용 (포트가 다를 수 있음)
docker-compose up -d postgres redis
# .env의 포트를 docker-compose.yml에 맞게 조정
```
