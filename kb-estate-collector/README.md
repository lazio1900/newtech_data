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
┌─────────────┐
│  Admin Web  │ (향후 구현)
└──────┬──────┘
       │
┌──────▼──────────┐
│   Admin API     │ FastAPI (26 routes)
│  (Port 8000)    │
└──────┬──────────┘
       │
       ├─── PostgreSQL (데이터 저장)
       │
       ├─── Redis (Queue/Cache)
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

- **API**: FastAPI + Uvicorn
- **Worker**: Celery + Redis
- **Database**: PostgreSQL + SQLAlchemy 2.0 + Alembic
- **Browser**: Playwright (chromium, headless)
- **HTTP Client**: httpx
- **Container**: Docker + Docker Compose

## 프로젝트 구조

```
kb-estate-collector/
├── src/
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
│   └── core/                       # 설정, DB, 로깅
│       ├── config.py
│       ├── database.py
│       └── logging.py
│
├── scripts/
│   └── run_api_discovery.py        # API 발견 CLI 도구
│
├── docker/                         # Dockerfiles
├── docs/                           # 프로젝트 문서
├── tests/                          # 테스트
├── docker-compose.yml
├── requirements.txt
└── alembic.ini
```

## 시작하기

### 1. 환경 설정

```bash
# Python 가상환경
python -m venv venv
venv\Scripts\activate    # Windows
# source venv/bin/activate  # Linux/Mac

# 의존성 설치
pip install -r requirements.txt
playwright install chromium
```

### 2. Docker Compose로 실행

```bash
# 전체 서비스 시작
docker-compose up -d

# DB 마이그레이션
docker-compose exec admin-api alembic upgrade head

# 로그 확인
docker-compose logs -f
```

### 3. 로컬 개발 (Docker 없이)

```bash
# DB/Redis만 Docker로
docker-compose up -d postgres redis

# API 서버
uvicorn src.admin_api.main:app --reload --port 8000

# Celery Worker (별도 터미널)
celery -A src.workers.celery_app worker --loglevel=info

# Celery Beat (별도 터미널)
celery -A src.workers.celery_app beat --loglevel=info
```

### 4. API 문서

- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 주요 기능

### 지역 기반 자동 수집

```bash
# 1. 강남구(11680) 아파트 단지 자동 발견
curl -X POST "http://localhost:8000/api/complexes/discover-region?region_code=11680"

# 2. 지역 전체 수집 (발견→시세→실거래가→매물)
curl -X POST "http://localhost:8000/api/jobs/run-region?region_code=11680"
```

### 데이터 조회

```bash
# KB시세
curl "http://localhost:8000/api/data/kb-prices?complex_id=1"

# CSV 내보내기
curl "http://localhost:8000/api/data/kb-prices/export?complex_id=1" > prices.csv

# 실거래가 / 매물
curl "http://localhost:8000/api/data/transactions?complex_id=1"
curl "http://localhost:8000/api/data/listings?complex_id=1"
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
| [04-다음-단계-가이드](docs/04-다음-단계-가이드.md) | Docker 테스트, 매물 API 파라미터 확인 등 |
| [05-개발-검증-결과](docs/05-개발-검증-결과.md) | API 디스커버리 결과, 코드 검증, 버그 수정 기록 |

## 라이선스

Private project - 내부 사용만 허용
