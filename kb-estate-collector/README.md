# KB Estate Data Collection System

KB부동산 아파트 단지 데이터 수집 시스템 - Playwright 기반 하이브리드 크롤링

## 중요 안내

> 이 프로젝트는 연구용입니다.
> 상업적 이용이 아닌 테스트이므로 컴플라이언스를 준수한 것으로 이해하세요

## 수집 데이터

| 데이터 | 설명 | 커넥터 | API 상태 |
|--------|------|--------|----------|
| **KB 시세** | 일반가, 상한가, 하한가 | `KBPriceConnector` | 검증완료 |
| **실거래가** | 최근 실거래 정보 (BasePrcInfoNew에서 추출) | `KBPriceConnector` | 검증완료 |
| **매물정보** | 호가, 면적, 층, 상태 (HTTP/2 필수) | `KBListingConnector` | 검증완료 |

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

본 레포는 **짝 프로젝트 [`newtech-platform`](../../newtech-platform) 과 같은 PostgreSQL/Redis 컨테이너를 공유**한다. platform 측 docker-compose 가 인프라를 소유하므로 platform 을 먼저 띄워야 한다. 자세한 배경은 [`INTEGRATION.md`](./INTEGRATION.md) 참조.

### 1. 사전 요구사항

- Docker Desktop
- (호스트 venv 디버그 모드를 쓸 때만) Python 3.11+, Node.js 22.12+

### 2. newtech-platform 기동 (공유 인프라 포함)

```bash
cd /Users/lmj/00_projects/newtech-platform
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d
```

postgres(5433) / redis(6379) 컨테이너가 `newtech-platform_default` 네트워크에 뜬다.

### 3. 본 레포 기동

```bash
cd /Users/lmj/00_projects/newtech_data/kb-estate-collector
docker compose up -d
# admin-api, celery-worker, celery-beat, frontend 네 컨테이너 기동
```

### 4. DB 마이그레이션 (최초 / 모델 변경 시)

```bash
docker compose exec admin-api alembic upgrade head
```

### 5. 접속

- **Admin Frontend**: http://localhost:5174
- **Admin API (Swagger)**: http://localhost:8000/docs

### 호스트(venv) 디버그 모드

PDB/IDE 디버거 부착이 필요할 때만 사용. 절차는 [`docs/06-프론트엔드-및-기동-가이드.md`](./docs/06-프론트엔드-및-기동-가이드.md) "호스트(venv) 디버그 모드" 섹션 참조. 도커 모드와 동시 실행 불가 (8000/5174 포트 충돌).

## 서비스 포트

| 서비스 | 포트 | 비고 |
|--------|------|------|
| PostgreSQL (Docker) | **5433** | platform compose 가 소유. 본 레포는 컨테이너 네트워크로 공유 |
| Redis (Docker) | 6379 | 동일 |
| Admin API (FastAPI) | 8000 | Swagger: /docs |
| Admin Frontend (Vite) | 5174 | API → :8000 프록시 |
| Celery Worker / Beat | - | Redis 브로커 |

## 주요 기능

### 웹 UI에서 사용

1. http://localhost:5173 접속
2. **단지 관리** → "지역 발견" → 시/도 선택 → 시/군/구 선택 → 단지 자동 발견/등록
3. **단지 관리** → 체크박스로 단지 선택 → "크롤링 실행" → 시세/실거래가/매물 즉시 수집
4. **실행 이력**에서 진행 상태 + 대상 단지 확인 (한국시간 KST 표시)
5. **데이터 탐색**에서 수집된 시세 차트/데이터 확인 + CSV 내보내기

### 전국 지역 지원

시/도(16개) → 시/군/구(120+개) 계층형 선택 UI 제공:
- 서울, 경기, 인천, 부산, 대구, 대전, 광주, 울산, 세종, 충북, 충남, 전북, 전남, 경북, 경남, 제주
- 시/도 클릭 시 해당 시/도 전체 시/군/구 일괄 선택
- 개별 시/군/구 세부 선택도 가능 (더블클릭으로 펼침)

### CLI로 사용

```bash
# 1. 강남구(11680) 아파트 단지 자동 발견
curl -X POST "http://localhost:8000/api/complexes/discover-region?region_code=11680"

# 2. 여러 단지 일괄 수집
curl -X POST "http://localhost:8000/api/complexes/batch-collect" \
  -H "Content-Type: application/json" \
  -d '{"complex_ids": [1, 2, 3]}'

# 3. 지역 전체 수집 (발견→시세→실거래가→매물)
curl -X POST "http://localhost:8000/api/jobs/run-region?region_code=11680"

# 4. 데이터 조회
curl "http://localhost:8000/api/data/kb-prices?complex_id=1"

# 5. CSV 내보내기
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
| [07-사용-가이드](docs/07-사용-가이드.md) | 웹 UI 사용법 (단지등록→수집→결과확인 전체 흐름) |

## 라이선스

Private project - 내부 사용만 허용
