# CLAUDE.md — newtech_data (kb-estate-collector)

이 파일은 본 레포에서 에이전트(Claude Code 등)가 따라야 할 **빌드 / 코딩 /
커밋 규칙**과 **반복 실수 차단 지시**를 모은다.

> 짝 프로젝트 `newtech-platform` 과의 관계, DB·포트 할당은 `INTEGRATION.md`
> 와 `docs/` 시리즈를 단일 출처로 한다. 충돌이 생기면 그 문서들이 우선.

---

## 1. 프로젝트 개요 (요약)

- 목적: **KB부동산 데이터 수집 시스템** (단지·시세·실거래·매물·주변시설 크롤링)
- 데이터 소비자: 짝 프로젝트 `newtech-platform` (대출 심사 서비스). 본 레포는 사용자 대면 서비스가 아님.
- 핵심 특성: KB부동산은 SPA + 비공개 API → Playwright 기반 하이브리드 크롤러
- 운영 모드: Admin API(FastAPI 8000) + Celery worker(prefork) + Celery Beat(RedBeat) + Frontend(Vite 5174)

## 2. newtech-platform 과의 관계 (필독)

본 레포는 데이터를 생산만 한다. 소비는 `newtech-platform` 의 책임.

### 2.1 역할 분담

| 항목 | newtech_data (이 레포) | newtech-platform |
|---|---|---|
| 위치 | `/Users/lmj/00_projects/newtech_data/kb-estate-collector` | `/Users/lmj/00_projects/newtech-platform` |
| 책임 | KB부동산 크롤링·적재 | 심사 워크플로 웹 서비스 (사용자/AI 분석) |
| 사용자 대면 | 관리 콘솔 (Admin API 8000 + Frontend 5174) | 일반 사용자 (FastAPI 8002 + Frontend 5173) |
| Celery | O (prefork, RedBeat) | X |

### 2.2 공유 인프라 — **newtech-platform 의 docker-compose 가 책임**

- PostgreSQL: **5433** / `kb_estate` / `kb_user`
- Redis: **6379** / DB 0 (브로커 + 결과 저장 + RedBeat 스케줄)

본 레포 `docker-compose.yml` 은 **postgres/redis 서비스를 갖지 않는다.**
admin-api / celery-worker / celery-beat / frontend 네 컨테이너만 정의하며,
`newtech-platform_default` 외부 네트워크에 합류해 platform 의 postgres/redis
컨테이너를 직접 사용한다 (서비스명 `postgres:5432`, `redis:6379` 로 연결).
따라서 platform 이 먼저 떠 있어야 본 레포 compose 가 기동된다.
**예외**: PDB/IDE 디버거를 붙이고 싶을 때만 호스트 venv 모드로 본 레포 코드를
도커 밖에서 실행 (단, 인프라는 여전히 platform docker 가 띄워줘야 함).

### 2.3 DB 테이블 소유권 (단일 출처: `INTEGRATION.md`)

| 소유자 | 테이블 | 접근 권한 |
|---|---|---|
| **newtech_data** | `complexes`, `areas`, `kb_prices`, `transactions`, `listings`, `crawl_jobs`, `crawl_runs`, `crawl_tasks`, `raw_payloads` | 본 레포 R/W |
| **newtech-platform** | `users`, `loan_applications`, `monitoring_loans`, `search_history`, `analysis_audit_logs` | 본 레포 **접근 금지** |

본 레포에서 platform 소유 테이블을 SELECT 하거나 마이그레이션에 포함하는 것은
금지. 두 레포는 같은 DB 안에 alembic 두 개를 별도 history 로 운영한다.

### 2.4 Alembic 분리

- 본 레포 version_table: **`alembic_version`** (default)
- newtech-platform version_table: `alembic_version_app`
- 본 레포는 본 레포 소유 테이블만 마이그레이션. autogenerate diff 에 platform
  테이블이 끼면 제거 후 커밋한다.

### 2.5 기동 순서 (도커 운영, 기본)

```bash
# 1) platform 전체 (postgres/redis 포함)
cd /Users/lmj/00_projects/newtech-platform
docker compose -f docker-compose.yml -f docker-compose.dev.yml up -d

# 2) 본 레포 (admin-api / celery-worker / celery-beat / frontend)
cd /Users/lmj/00_projects/newtech_data/kb-estate-collector
docker compose up -d
# Admin API → http://localhost:8000/docs, Frontend → http://localhost:5174
```

종료는 역순(본 레포 → platform). platform 을 먼저 내리면 본 레포 컨테이너가
사용 중인 네트워크가 끊긴다.

마이그레이션은 컨테이너 안에서 실행:
```bash
docker compose exec admin-api alembic upgrade head
docker compose exec admin-api alembic revision --autogenerate -m "..."
```

호스트(venv) 디버그 모드가 필요하면 `INTEGRATION.md` 의 "호스트(venv) 단독 디버그"
섹션 참조. 도커 모드와 동시 실행 불가 (포트 충돌).

## 3. 디렉토리 구조

```
src/
  admin_api/          # FastAPI Admin API (8000)
    main.py
    routers/          # complexes, jobs, runs, data_explorer, batches
  connectors/         # 외부 데이터 소스 클라이언트
    base.py           # BaseConnector (재시도/레이트리밋)
    kb_base.py        # KBBaseConnector (httpx + Playwright 폴백)
    kb_*.py           # 시세/실거래/매물/학군/주변시설
    molit_transaction.py / osm_nature.py
    kb_endpoints.py
  browser/            # Playwright 세션 / 안티 디텍션
  workers/
    celery_app.py     # Celery + RedBeat 설정
    tasks.py          # 수집/마감/좀비 청소 태스크
  services/           # 비즈니스 로직 (complex_discovery 등)
  models/             # SQLAlchemy ORM (complex, crawl, facility, price_data)
  core/               # config, database, logging, time
  alembic/            # 마이그레이션 (collector 소유 테이블만)
frontend/             # React 19 + Vite + TS + Tailwind + shadcn + react-router
docs/                 # 01~09 시리즈 (개요/아키텍처/교훈/사용 가이드 등)
scripts/              # 백필/탐사 스크립트 (probe_*.py, backfill_*.py)
INTEGRATION.md
docker-compose.yml    # admin-api/celery/frontend 컨테이너만 정의. postgres/redis 는 platform 네트워크에서 공유
```

레포 루트의 `test_apis*.py`, `capture_*.py`, `discovery_*.json`, `*.png` 등은
**초기 API 탐색 자산**이다. 현재 운영 코드와 무관하므로 수정·삭제하지 말고
참조용으로만 둔다.

## 4. 빌드 / 실행

자세한 절차는 `docs/06-프론트엔드-및-기동-가이드.md`, `docs/07-사용-가이드.md`.

### 포트 (고정 — 임의 변경 금지, INTEGRATION.md)
| 서비스 | 포트 |
|---|---|
| PostgreSQL (공유) | 5433 |
| Redis (공유) | 6379 |
| **newtech_data** Admin API | **8000** |
| **newtech_data** Frontend | **5174** |
| newtech-platform Backend | 8002 |
| newtech-platform Frontend | 5173 |

### Lint / 검증
- Backend: `ruff`, `black`, `mypy` 설치됨. 변경 후 `python -c "import src.admin_api.main"` 또는 uvicorn 기동으로 import 검증
- Frontend: `npm run lint`, `npm run build` 통과 필수
- 크롤러 단독 검증: `scripts/probe_*.py` 로 외부 API/페이지 응답 구조 확인 후 connector 의 `parse()` 수정

### 마이그레이션 (도커 모드)
```bash
docker compose exec admin-api alembic revision --autogenerate -m "add foo column"
docker compose exec admin-api alembic upgrade head
docker compose exec admin-api alembic downgrade -1
docker compose exec admin-api alembic current
```
호스트 venv 모드에서는 `docker compose exec admin-api` 를 떼고 그대로 실행.
autogenerate 결과에 platform 소유 테이블(`users`, `loan_applications` 등)이 끼면
**전부 제거**한 뒤 커밋한다.

## 5. 코딩 규칙

### 공통
- **지정 파일만 수정한다.** 사용자가 지목하지 않은 파일·디렉토리는 백업/참고용으로 간주하고 건드리지 않는다. 특히 레포 루트의 탐사 자산(`test_apis*.py`, `capture_*.py`, `discovery_*.json`, 스크린샷)은 손대지 않는다.
- 사용자 요청 범위 밖의 리팩토링·정리·추상화 도입은 하지 않는다. 같은 줄 3번 반복이 섣부른 추상화보다 낫다.
- 외부 경계(웹 입력, 외부 API 응답)에만 방어 코드를 둔다. 내부 호출과 프레임워크 보증은 신뢰한다.
- 주석은 기본적으로 쓰지 않는다. **왜**가 비자명할 때만 한 줄로.

### 백엔드 (FastAPI / SQLAlchemy / Celery)
- 새 라우터는 `src/admin_api/routers/` 에 추가하고 `main.py` 에 `include_router` 등록.
- DB 세션은 `src/core/database.py` 의 `DatabaseTask` / 의존성 사용. 라우터/태스크에서 새 engine 생성 금지.
- 비-PK UNIQUE 제약에 대해 UPSERT 가 필요하면 `from sqlalchemy.dialects.postgresql import insert as pg_insert` + `.on_conflict_do_nothing(index_elements=[...])`. **`db.merge()` 는 PK 기반이라 UPSERT 가 아니다** (§7 anti-pattern #1).
- 커넥터의 `parse()` 는 **후보 키 리스트** 패턴 사용. 단일 키만 기대하면 KB 응답 변경 시 즉시 깨짐 (§7 #2).
- 외부 API 응답 구조가 불확실하면 먼저 `scripts/probe_*.py` 로 확인. 추측해서 parse 코드 짜지 말 것.
- Celery 태스크는 **prefork pool 유지** (threads pool 은 `DatabaseTask._db` 가 class var 라 race). macOS 에서는 `OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES` 환경변수 필수 (§7 #4).
- async ↔ sync 브릿지는 `asyncio.new_event_loop()` 로 매 호출마다 새 루프. `asyncio.run()` 을 running loop 안에서 부르면 폭발.
- 매물(`listings`) 수집은 "이번에 안 보인 매물 → REMOVED" 상태 전이를 유지. 단순 INSERT/UPDATE 로 바꾸지 말 것 (§7 #5).
- 시간/타임존: `src/core/time.py` 의 KST 헬퍼 재사용. naive datetime 저장 금지.
- 동적 cron schedule (`crawl_jobs.cron_schedule`) 변경 시 `_sync_redbeat_entry()` 호출. RedBeat 가 Redis 폴링으로 자동 반영 — beat 재기동 시도하지 말 것.

### 안티 디텍션 / 레이트리밋
- KB API 호출은 `KBBaseConnector` 의 레이트리밋(`KB_RATE_LIMIT_PER_MINUTE=30`) 통과. 우회 금지.
- Playwright 세션은 `src/browser/` 의 UA 풀 + `navigator.webdriver` 위장 + 랜덤 딜레이(2~5s)를 그대로 사용. "테스트라서" 끄지 말 것.

### 프론트엔드 (React 19 / Vite / TS / Tailwind / shadcn)
- API 호출은 axios + `@tanstack/react-query`. 컴포넌트에서 fetch 직접 호출 금지.
- 라우팅: `react-router-dom` v7. 새 페이지는 기존 라우트 구조에 맞춰 추가.
- UI 컴포넌트는 shadcn 패턴 (`components.json` 기준). 외부 UI 라이브러리 추가 전 기존 의존성으로 가능한지 먼저 확인.
- 환경변수는 `VITE_*` 접두사.

## 6. 커밋 규칙

기존 로그 스타일 (한국어, 한 줄 요약 + 다음 작업 힌트):
```
commit 2026-05-08 : 크롤링 개선 & 디자인 처리 전 커밋
commit 2026-05-06 : 주변시설(학군, 지하철, 병원) 수집 완료
commit7 : 한국시간 변경, 실행이력 ui 변경 등 .. 다음 업무는 지역발견 기능 삭제
```

원칙:
- **사용자가 명시적으로 커밋을 지시할 때만** 커밋한다. 작업 종료 시 자동 커밋 금지.
- 한 줄 요약은 변경의 **목적/도메인** 중심. "what" 보다 "why".
- `.env`, API_KEY, Sentry DSN, Slack Webhook, 대용량 캡처(JSON/PNG)는 staging 금지. `git add -A` / `git add .` 지양, 파일 단위 추가.
- pre-commit hook 실패 시 **amend 하지 말고** 새 커밋으로 수정.
- 푸시는 명시적 지시가 있을 때만.

## 7. 반복 실수 차단 (Anti-patterns)

> **이 섹션은 살아있는 체크리스트다.** 같은 실수가 두 번째로 나오면 여기에 추가한다.
> 형식: `### N. <한 줄 규칙>` + **상황** / **하지 말 것** / **할 것**.
> 기존 항목 상당수는 `docs/03-교훈-및-주의사항.md` 에서 옮겨왔다.

### 1. `db.merge()` 를 UPSERT 로 쓰지 말 것
- **상황**: 비-PK UNIQUE 인덱스가 있는 모델(`Transaction`, `ComplexFacility` 등)에 신규 row 저장
- **하지 말 것**: `session.merge(obj)` — PK 기반이라 UNIQUE 위반을 막지 못함 → IntegrityError 폭발
- **할 것**: `pg_insert(Model).values(...).on_conflict_do_nothing(index_elements=[...])` 로 dialect-specific UPSERT. PostgreSQL UNIQUE 는 NULL ≠ NULL 임을 기억할 것(`floor=NULL` 중복 가능).

### 2. KB 응답 키를 하나만 가정하지 말 것
- **상황**: 커넥터 `parse()` 작성
- **하지 말 것**: `data["dealAmt"]` 한 줄. KB 가 한국어 키(`매매가`) ↔ 영어 키(`general_price`, `avgPrc`) 사이를 자주 갈아탄다.
- **할 것**: 후보 키 리스트 순회 (`for key in ["dealAmt", "general_price", "avgPrc", "매매가"]: ...`). 응답 구조가 의심되면 먼저 `scripts/probe_*.py` 실행.

### 3. SPA 페이지를 `requests` / `httpx` / `WebFetch` 로 긁지 말 것
- **상황**: 새 KB 페이지/유사 사이트에서 데이터 추출 시도
- **하지 말 것**: 정적 HTML fetch — Vue SPA 라 빈 껍데기만 반환됨.
- **할 것**: 우선 Playwright 로 렌더링 후 XHR 인터셉트 → 발견된 내부 API 를 httpx 로 호출 시도 → 실패 시 Playwright 폴백 (`KBBaseConnector` 패턴).

### 4. macOS Celery prefork 에서 fork-safety 환경변수 누락
- **상황**: 호스트(venv) 디버그 모드로 워커 기동 시 `SIGSEGV` 빈발 → 좀비 task 누적 → 수집 멈춤
- **하지 말 것**: `celery worker --pool=prefork` 만 실행.
- **할 것**: `OBJC_DISABLE_INITIALIZE_FORK_SAFETY=YES PYTHONFAULTHANDLER=1` 환경변수 함께 export. threads pool 은 `DatabaseTask._db` race 위험으로 금지.
- **참고**: 도커 운영 모드(기본) 에서는 컨테이너가 Linux 라 해당 변수가 필요 없다. 호스트 venv 모드에서만 유효.

### 5. 매물 수집을 단순 upsert 로 바꾸지 말 것
- **상황**: `collect_kb_listing_task` 리팩토링
- **하지 말 것**: 이번 응답을 그대로 INSERT/UPDATE 하고 끝.
- **할 것**: 이번 수집의 `seen_ids` 추적 → 기존 ACTIVE 중 `seen_ids` 에 없는 매물은 `REMOVED` 로 상태 전이 → 다시 보이면 `ACTIVE` 복원. "없음"도 정보다.

### 6. 좀비 RUNNING task/run 청소 책임을 빼먹지 말 것
- **상황**: 워커가 SIGSEGV / OOM / Ctrl+C 로 죽음
- **하지 말 것**: broker heartbeat 만 믿고 방치 → `_finalize_run_if_complete` 가 영원히 안 끝남.
- **할 것**: `cleanup_zombie_runs` 주기 태스크(5분)를 항상 유지. task timeout 10분 / run timeout 60분 정책. RedBeat 가 자동 픽업하도록 `celery_app.conf.beat_schedule` 에 정적 등록.

### 7. 인프라(postgres/redis)를 본 레포 docker-compose 에 다시 추가하지 말 것
- **상황**: 개발 환경 셋업 / docker-compose.yml 정리
- **하지 말 것**: 본 레포 compose 에 `postgres` / `redis` 서비스를 다시 추가 → platform 의 컨테이너와 호스트 포트(5433/6379) 충돌 + 두 DB 인스턴스로 분리되어 데이터 공유 깨짐.
- **할 것**: 본 레포 compose 는 admin-api / celery-worker / celery-beat / frontend 네 컨테이너만 정의. `networks.default` 가 `newtech-platform_default` 를 `external: true` 로 참조하게 둔다. platform 이 먼저 떠야 본 레포 compose 가 기동된다.

### 8. platform 소유 테이블을 마이그레이션에 포함하지 말 것
- **상황**: `alembic revision --autogenerate` 결과에 `users`, `loan_applications` 등이 diff 로 잡힘
- **하지 말 것**: 그대로 커밋 → platform 의 데이터를 본 레포가 덮어쓰는 사고.
- **할 것**: autogenerate 결과에서 platform 소유 테이블 관련 op 모두 제거. `src/alembic/env.py` 가 `target_metadata` 를 collector 모델만 갖도록 유지.

### 9. 동적 cron schedule 변경 후 beat 재기동 시도하지 말 것
- **상황**: `crawl_jobs.cron_schedule` 변경 후 적용
- **하지 말 것**: `celery beat` 재기동.
- **할 것**: `_sync_redbeat_entry()` 호출만으로 충분. RedBeat 가 Redis 폴링(15초)으로 자동 반영. 정적 task 는 `celery_app.conf.beat_schedule` 에 두면 RedBeat 도 자동 픽업.

### 10. 부모 트랜잭션 commit 전에 자식 Celery 태스크 enqueue 하지 말 것
- **상황**: `run_kb_collection` / `run_region_collection` 의 for 루프에서 `ensure_complex_areas()` 로 신규 Area row 를 INSERT 한 직후, 같은 단지의 면적별 `collect_kb_price_task.delay(...)` 를 enqueue
- **하지 말 것**: `db.flush()` 만 하고 자식 태스크 `.delay()` 호출. prefork worker 가 별도 트랜잭션을 갖기 때문에 자식이 자기 세션으로 `Area.get(area_id)` 해도 uncommitted row 가 안 보임 → `Area X: kb_area_code not found` race fail. Run #5(81건), #51(52건), #53(416건) 모두 이 패턴. 전체 실패 사유 중 60% 차지.
- **할 것**: 자식 `.delay()` 호출 직전에 부모가 `db.commit()`. ensure_* 단계가 끝난 뒤 단지 단위로 commit 하면 단지 단위 atomicity 도 유지된다. `ensure_complex_areas()` 내부에서 commit 하지 말 것 — 호출 컨텍스트(부모)가 트랜잭션 경계를 책임진다는 의미 단일화.

<!-- 다음 항목 추가 양식
### N. <한 줄 규칙>
- **상황**:
- **하지 말 것**:
- **할 것**:
-->

## 8. 단일 출처 (Source of Truth)

| 주제 | 문서 |
|---|---|
| newtech-platform 연동·포트·DB 소유권 | `INTEGRATION.md` |
| 프로젝트 개요 | `docs/01-프로젝트-개요.md` |
| 아키텍처 상세 | `docs/02-아키텍처-상세.md` |
| 교훈/주의사항 (확장 버전) | `docs/03-교훈-및-주의사항.md` |
| 다음 단계 | `docs/04-다음-단계-가이드.md` |
| 개발 검증 결과 | `docs/05-개발-검증-결과.md` |
| 기동 가이드 | `docs/06-프론트엔드-및-기동-가이드.md` |
| 사용 가이드 | `docs/07-사용-가이드.md` |
| 크롤링 안정성 보강 (2026-05) | `docs/08-크롤링-안정성-보강-2026-05.md` |
| 현황 요약 | `docs/09-2026-05-현황-요약.md` |

본 CLAUDE.md 와 위 문서가 충돌하면 **위 문서가 우선**한다. 본 파일은 에이전트용
규칙 모음이며, 상세 설계/결정 기록은 `docs/` 시리즈에 둔다.
