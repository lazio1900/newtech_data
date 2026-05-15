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
> `newtech_data`의 docker-compose는 **postgres/redis 서비스를 갖지 않으며**, `newtech-platform_default` 네트워크에 외부 참조로 합류해 platform 의 컨테이너를 직접 사용합니다. 따라서 platform 이 먼저 떠 있어야 합니다.

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

`.env` 는 **호스트에서 직접(venv) 실행할 때만** 참조됩니다. docker compose 로 띄울 때는 `docker-compose.yml` 의 `environment` 블록이 우선합니다.

```env
# 호스트에서 venv 로 실행 시 (디버그 용도)
DATABASE_URL=postgresql://kb_user:change-me-in-production@localhost:5433/kb_estate
REDIS_URL=redis://localhost:6379/0
CELERY_BROKER_URL=redis://localhost:6379/0
CELERY_RESULT_BACKEND=redis://localhost:6379/0

# 이 프로젝트 전용 포트
API_HOST=0.0.0.0
API_PORT=8000
```

비밀번호(`change-me-in-production`)는 `newtech-platform/.env` 의 `POSTGRES_PASSWORD` 와 일치해야 합니다.

## 기동 순서 (도커 운영)

```bash
# 1. 공유 인프라 + platform 자체 (newtech-platform)
cd /Users/lmj/00_projects/newtech-platform
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d

# 2. newtech_data 스택 (admin-api / celery-worker / celery-beat / frontend)
cd /Users/lmj/00_projects/newtech_data/kb-estate-collector
docker compose up -d
# Admin API → http://localhost:8000/docs
# Admin Frontend → http://localhost:5174
```

종료 순서는 역순(newtech_data → newtech-platform). platform 을 먼저 내리면 kb 컨테이너가 사용 중인 네트워크가 끊깁니다.

### 알렘빅 마이그레이션

```bash
docker compose exec admin-api alembic upgrade head
docker compose exec admin-api alembic revision --autogenerate -m "..."
```

## 호스트(venv) 단독 디버그

특정 코드를 PDB / IDE 디버거로 잡고 싶을 때만 사용. 인프라(postgres/redis)는 여전히 platform docker 가 띄워주고 있어야 하며, 본 레포의 코드만 호스트에서 직접 실행합니다.

```bash
source .venv/bin/activate
uvicorn src.admin_api.main:app --host 0.0.0.0 --port 8000 --reload   # 별도 터미널 1
OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES PYTHONFAULTHANDLER=1 \
  celery -A src.workers.celery_app worker --pool=prefork --concurrency=4 --loglevel=info   # 별도 터미널 2
celery -A src.workers.celery_app beat --loglevel=info                # 별도 터미널 3
cd frontend && npm run dev                                           # 별도 터미널 4
```

이 모드는 docker compose 와 동시 사용 불가 (8000/5174 포트 충돌). 한 모드만 골라 실행합니다.
