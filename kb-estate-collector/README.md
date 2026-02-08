# KB Estate Data Collection System

KB부동산 아파트 단지 데이터 수집 시스템 - 전문 수집 시스템 아키텍처

## ⚠️ 중요 안내

> **법적 컴플라이언스 필수**
> 
> 이 프로젝트는 KB부동산 데이터 수집을 포함합니다. 실제 운영 전 다음 사항을 반드시 확인하세요:
> - KB부동산 이용약관 및 robots.txt 확인
> - 데이터 수집 권한 확보 (공식 API, 제휴 계약 등)
> - 개인정보 수집/저장 금지 원칙 준수
> 
> 현재 구현된 KB 커넥터는 **MOCK 구현**입니다.

## 아키텍처

```
┌─────────────┐
│  Admin Web  │ (향후 구현)
└──────┬──────┘
       │
┌──────▼──────────┐
│   Admin API     │ FastAPI
│  (Port 8000)    │
└──────┬──────────┘
       │
       ├─── PostgreSQL (데이터 저장)
       │
       ├─── Redis (Queue/Cache)
       │
       └─── Celery Workers (데이터 수집)
                 │
                 ├─ KB Price Connector
                 ├─ KB Listing Connector
                 └─ MOLIT Transaction Connector
```

## 기술 스택

- **API**: FastAPI + Uvicorn
- **Worker**: Celery + Redis
- **Database**: PostgreSQL + SQLAlchemy + Alembic
- **Container**: Docker + Docker Compose

## 시작하기

### 1. 환경 설정

```bash
# 환경 변수 파일 생성
cp .env.example .env
# .env 파일을 편집하여 필요한 값 설정
```

### 2. Docker Compose로 전체 시스템 실행

```bash
# 전체 서비스 시작
docker-compose up -d

# 로그 확인
docker-compose logs -f

# 특정 서비스만 시작
docker-compose up -d postgres redis
```

### 3. 데이터베이스 마이그레이션

```bash
# 초기 마이그레이션 생성
docker-compose exec admin-api alembic revision --autogenerate -m "Initial migration"

# 마이그레이션 적용
docker-compose exec admin-api alembic upgrade head
```

### 4. API 문서 확인

브라우저에서 다음 주소로 접속:
- Swagger UI: http://localhost:8000/docs
- ReDoc: http://localhost:8000/redoc

## 로컬 개발 (Docker 없이)

### 1. Python 가상환경 설정

```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

### 2. PostgreSQL 및 Redis 설치/실행

```bash
# Docker로 DB만 실행
docker-compose up -d postgres redis
```

### 3. 마이그레이션 및 API 실행

```bash
# 마이그레이션
alembic upgrade head

# API 서버 실행
uvicorn src.admin_api.main:app --reload --port 8000

# 별도 터미널에서 Celery Worker 실행
celery -A src.workers.celery_app worker --loglevel=info

# 별도 터미널에서 Celery Beat 실행
celery -A src.workers.celery_app beat --loglevel=info
```

## 주요 기능

### 1. 단지 관리
- 단지 등록/수정/삭제
- 수집 우선순위 설정
- 면적 타입 관리

### 2. 수집 작업 관리
- Job 생성 및 스케줄 설정
- 수동 실행, 일시 중지/재개
- 실행 이력 조회

### 3. 데이터 탐색
- KB 시세, 실거래가, 매물 조회
- 필터링 및 정렬
- CSV 내보내기

### 4. 운영 기능
- 실행 로그 및 에러 추적
- 태스크 단위 재시도
- 데이터 품질 검증 (향후)

## API 엔드포인트 예시

```bash
# 단지 목록 조회
curl http://localhost:8000/api/complexes

# 단지 등록
curl -X POST http://localhost:8000/api/complexes \
  -H "Content-Type: application/json" \
  -d '{
    "name": "래미안아파트",
    "address": "서울시 강남구",
    "priority": "high"
  }'

# Job 즉시 실행
curl -X POST http://localhost:8000/api/jobs/1/run

# KB 시세 조회
curl "http://localhost:8000/api/data/kb-prices?complex_id=1"

# CSV 내보내기
curl "http://localhost:8000/api/data/kb-prices/export?complex_id=1" > prices.csv
```

## 프로젝트 구조

```
kb-estate-collector/
├── src/
│   ├── admin_api/          # FastAPI 앱
│   │   ├── main.py
│   │   └── routers/        # API 라우터
│   ├── workers/            # Celery workers
│   │   ├── celery_app.py
│   │   └── tasks.py        # 수집 태스크
│   ├── connectors/         # 데이터 소스 커넥터
│   │   ├── base.py
│   │   ├── kb_price.py
│   │   ├── kb_listing.py
│   │   └── molit_transaction.py
│   ├── models/             # SQLAlchemy 모델
│   │   ├── complex.py
│   │   ├── price_data.py
│   │   └── crawl.py
│   ├── core/               # 설정 및 유틸리티
│   │   ├── config.py
│   │   ├── database.py
│   │   └── logging.py
│   └── alembic/            # DB 마이그레이션
├── docker/                 # Dockerfiles
├── tests/                  # 테스트
├── docker-compose.yml
├── requirements.txt
└── README.md
```

## 개발 도구

### 코드 포맷팅
```bash
black src/
ruff check src/
```

### 타입 체킹
```bash
mypy src/
```

### 테스트 (향후)
```bash
pytest tests/
```

## 다음 단계

### Phase 2 구현 항목
- [ ] 실제 KB API 연동 (권한 확보 후)
- [ ] 국토부 OpenAPI 실거래가 수집
- [ ] 데이터 품질 검증 로직
- [ ] RawPayload 저장 (S3/MinIO)
- [ ] 알림 기능 (Slack, Email)
- [ ] RBAC 및 사용자 관리
- [ ] Audit Log
- [ ] Admin Web UI (React/Vue)

## 라이선스

Private project - 내부 사용만 허용

## 문의

프로젝트 관련 문의사항은 팀 내부 채널을 통해 연락 주세요.
