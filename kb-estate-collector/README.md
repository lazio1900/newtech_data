# KB Estate Data Collection System

KB부동산 아파트 단지 데이터 수집 시스템 - Playwright 기반 하이브리드 크롤링

## 중요 안내

> 이 프로젝트는 연구용입니다.
> 상업적 이용이 아닌 테스트이므로 컴플라이언스를 준수한 것으로 이해하세요

## 수집 데이터

| 데이터 | 설명 | 커넥터 | API 상태 |
|--------|------|--------|----------|
| **KB 시세** | 일반가, 상한가, 하한가 | `KBPriceConnector` | 검증완료 |
| **실거래가** | 계약일, 거래가, 면적, 층 | `KBTransactionConnector` | 경로확인 |
| **매물정보** | 호가, 면적, 층, 상태 | `KBListingConnector` | 경로확인 |

## 아키텍처

```
┌───────────────────┐
│   Frontend (Web)  │ React 19 + Vite 7 + Tailwind v4
│  (Port 5173/5174) │ shadcn/ui, TanStack Query, Recharts
└────────┬──────────┘
         │ /api proxy
┌────────▼──────────┐
│   Admin API       │ FastAPI (26 routes)
│   (Port 8000)     │
└────────┬──────────┘
         │
         ├─── PostgreSQL (Port 5433, Docker)
         │
         ├─── Redis (Port 6379, Docker)
         │
         └─── Celery Workers (데이터 수집)
                   │
                   ├─ KBPriceConnector       (KB시세)
                   ├─ KBTransactionConnector  (실거래가)
                   ├─ KBListingConnector      (매물)
                   └─ MolitTransactionConnector (국토부 OpenAPI)
                        │
                  ┌─────▼─────────┐
                  │ 하이브리드 전략  │
                  │ HTTP 우선      │ ← httpx 직접 API 호출
                  │ Browser 폴백   │ ← Playwright 브라우저 렌더링
                  └───────────────┘
```

## 기술 스택

### Backend
- **API**: FastAPI + Uvicorn
- **Worker**: Celery + Redis
- **Database**: PostgreSQL + SQLAlchemy 2.0 + Alembic
- **Browser**: Playwright (chromium, headless)
- **HTTP Client**: httpx
- **Container**: Docker + Docker Compose

### Frontend
- **Framework**: React 19 + TypeScript 5.7
- **Build**: Vite 7.3
- **Styling**: Tailwind CSS v4 + shadcn/ui
- **Data**: TanStack Query v5 (자동 캐싱/리페치)
- **Charts**: Recharts (시세 추이, 실행 통계)
- **Routing**: React Router v7

## 프로젝트 구조

```
kb-estate-collector/
├── src/                            # 백엔드 소스
│   ├── browser/                    # 브라우저 자동화
│   │   ├── stealth.py              # 안티 디텍션 (UA풀, webdriver 위장)
│   │   ├── session_manager.py      # Playwright 싱글턴 세션 관리
│   │   └── api_discovery.py        # KB API 엔드포인트 자동 발견
│   │
│   ├── connectors/                 # 데이터 수집 커넥터
│   │   ├── base.py                 # 추상 베이스 (재시도, 레이트리밋)
│   │   ├── kb_base.py              # KB 하이브리드 베이스 (HTTP→Browser)
│   │   ├── kb_endpoints.py         # API 엔드포인트 정의 (검증 완료)
│   │   ├── kb_price.py             # KB 시세 커넥터
│   │   ├── kb_transaction.py       # KB 실거래가 커넥터
│   │   ├── kb_listing.py           # KB 매물 커넥터
│   │   └── molit_transaction.py    # 국토교통부 API (기존)
│   │
│   ├── services/                   # 비즈니스 서비스
│   │   └── complex_discovery.py    # 지역 기반 단지 자동 발견
│   │
│   ├── workers/                    # Celery 태스크
│   │   ├── celery_app.py           # Beat 스케줄, 브라우저 정리
│   │   └── tasks.py                # 시세/실거래가/매물/지역수집 태스크
│   │
│   ├── models/                     # SQLAlchemy 모델
│   │   ├── complex.py              # Complex, Area
│   │   ├── price_data.py           # KBPrice, Transaction, Listing
│   │   └── crawl.py                # CrawlJob, CrawlRun, CrawlTask
│   │
│   ├── admin_api/                  # FastAPI 라우터
│   │   ├── main.py
│   │   └── routers/
│   │       ├── complexes.py        # 단지 CRUD + discover-region
│   │       ├── jobs.py             # 작업 관리 + run-region
│   │       ├── runs.py             # 실행 이력
│   │       └── data_explorer.py    # 데이터 조회/내보내기
│   │
│   ├── alembic/                    # DB 마이그레이션
│   │   ├── env.py
│   │   └── versions/
│   │
│   └── core/                       # 설정, DB, 로깅
│       ├── config.py
│       ├── database.py
│       └── logging.py
│
├── frontend/                       # 프론트엔드 소스
│   ├── src/
│   │   ├── api/                    # API 클라이언트 (axios)
│   │   ├── hooks/                  # TanStack Query 커스텀 훅
│   │   ├── types/                  # TypeScript 타입
│   │   ├── lib/                    # 유틸리티 (포맷, 상수)
│   │   ├── components/
│   │   │   ├── ui/                 # shadcn/ui (13개)
│   │   │   ├── layout/            # AppShell, Sidebar, PageHeader
│   │   │   ├── shared/            # StatusBadge, EmptyState, etc.
│   │   │   └── charts/            # PriceTrendChart, RunStatsChart
│   │   └── pages/
│   │       ├── DashboardPage.tsx   # 대시보드
│   │       ├── complexes/          # 단지 관리 (목록/상세/등록)
│   │       ├── jobs/               # 수집 작업 (목록/생성)
│   │       ├── runs/               # 실행 이력 (목록/상세)
│   │       └── data/               # 데이터 탐색 (시세/실거래/매물)
│   ├── vite.config.ts
│   └── package.json
│
├── scripts/
│   └── run_api_discovery.py        # API 발견 CLI 도구
│
├── docker/                         # Dockerfiles
├── docs/                           # 프로젝트 문서
├── tests/                          # 테스트
├── docker-compose.yml
├── requirements.txt
├── alembic.ini
└── .env
```

## 빠른 시작

### 1. 사전 요구사항

- Python 3.11+
- Node.js 22.12+
- Docker Desktop

### 2. 인프라 시작

```bash
cd kb-estate-collector

# PostgreSQL + Redis (Docker)
docker-compose up -d postgres redis

# 상태 확인
docker-compose ps
```

> **주의**: 로컬에 PostgreSQL이 설치되어 있으면 포트 5432 충돌이 발생합니다.
> `docker-compose.yml`의 PostgreSQL 포트가 `5433:5432`로 설정되어 있습니다.

### 3. 환경 설정

```bash
# .env 파일 생성 (.env.example 참고)
cp .env.example .env
# DATABASE_URL의 포트를 5433으로 수정
```

### 4. DB 마이그레이션

```bash
pip install -r requirements.txt

# 마이그레이션 생성 + 적용
python -m alembic revision --autogenerate -m "Initial schema"
python -m alembic upgrade head
```

### 5. 백엔드 시작

```bash
# FastAPI 서버
uvicorn src.admin_api.main:app --host 0.0.0.0 --port 8000 --reload

# Celery Worker (별도 터미널)
celery -A src.workers.celery_app worker --loglevel=info --pool=solo
```

> **Windows**: Celery에 `--pool=solo` 필수 (fork 미지원)

### 6. 프론트엔드 시작

```bash
cd frontend
npm install
npm run dev
```

### 7. 접속

- **웹 UI**: http://localhost:5173
- **Swagger API**: http://localhost:8000/docs

## 서비스 포트

| 서비스 | 포트 | 비고 |
|--------|------|------|
| PostgreSQL (Docker) | **5433** | 로컬 PG 충돌 방지 |
| Redis (Docker) | 6379 | |
| FastAPI | 8000 | Swagger: /docs |
| Celery Worker | - | Redis 브로커 |
| Frontend (Vite) | 5173/5174 | API → :8000 프록시 |

## 주요 기능

### 웹 UI에서 사용

1. http://localhost:5173 접속
2. **단지 관리** → "지역 발견" → 서울 구 코드 입력 (예: 강남구 `11680`) → 단지 자동 등록
3. **수집 작업** → "지역 수집" → 시세/실거래가/매물 수집 시작
4. **실행 이력**에서 진행 상태 확인
5. **데이터 탐색**에서 수집된 시세 차트/데이터 확인 + CSV 내보내기

### CLI로 사용

```bash
# 1. 강남구(11680) 아파트 단지 자동 발견
curl -X POST "http://localhost:8000/api/complexes/discover-region?region_code=11680"

# 2. 지역 전체 수집 (발견→시세→실거래가→매물)
curl -X POST "http://localhost:8000/api/jobs/run-region?region_code=11680"

# 3. 데이터 조회
curl "http://localhost:8000/api/data/kb-prices?complex_id=1"

# 4. CSV 내보내기
curl "http://localhost:8000/api/data/kb-prices/export?complex_id=1" > prices.csv
```

### KB API 직접 테스트 (DB 없이)

```bash
python -c "
import httpx
r = httpx.get('https://api.kbland.kr/land-price/price/BasePrcInfoNew',
    params={'단지기본일련번호': '12', '면적일련번호': '127753'},
    headers={'Referer': 'https://kbland.kr', 'Origin': 'https://kbland.kr'})
sise = r.json()['dataBody']['data']['시세'][0]
print(f'일반가: {sise[\"매매일반거래가\"]:,}만원')
print(f'상한가: {sise[\"매매상한가\"]:,}만원')
print(f'하한가: {sise[\"매매하한가\"]:,}만원')
"
```

## 문서

| 문서 | 설명 |
|------|------|
| [01-프로젝트-개요](docs/01-프로젝트-개요.md) | 목적, 기술 스택, 프로젝트 구조 |
| [02-아키텍처-상세](docs/02-아키텍처-상세.md) | 커넥터 상속 구조, 데이터 흐름, Celery 태스크 |
| [03-교훈-및-주의사항](docs/03-교훈-및-주의사항.md) | SPA 크롤링, 안티 디텍션, async/sync 등 |
| [04-다음-단계-가이드](docs/04-다음-단계-가이드.md) | 테스트 시나리오, 남은 작업 |
| [05-개발-검증-결과](docs/05-개발-검증-결과.md) | API 디스커버리 결과, 코드 검증, 버그 수정 |
| [06-프론트엔드-및-기동-가이드](docs/06-프론트엔드-및-기동-가이드.md) | 프론트엔드 구조, 전체 기동 가이드, 트러블슈팅 |

## 라이선스

Private project - 내부 사용만 허용
