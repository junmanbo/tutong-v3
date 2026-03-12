# AutoTrade Platform (tutong-v3)

국내 증권사(한국투자증권, 키움증권)와 글로벌 거래소(바이낸스, 업비트)를 하나의 웹 서비스에서 통합 운영하는 자동 매매 플랫폼입니다.  
`fastapi/full-stack-fastapi-template`를 기반으로 확장했으며, 봇 실행을 위한 독립 `bot_engine` 서비스를 포함합니다.

## 핵심 기능

- 거래소/증권사 계좌 연동 (API Key 기반)
- 트레이딩 봇 생성/시작/중지/삭제
- 5개 봇 전략 지원
  - `spot_grid`
  - `snowball`
  - `rebalancing`
  - `spot_dca`
  - `algo_orders`
- 대시보드에서 자산/봇 상태 조회
- API Key AES-256-GCM 암호화 저장

## 시스템 아키텍처

- Frontend: Vite + React + TypeScript + TanStack Router/Query + shadcn/ui
- Backend: FastAPI + SQLModel + Alembic + PostgreSQL
- Bot Engine: Celery Worker + APScheduler + Redis
- Exchange Integration:
  - Binance/Upbit: `ccxt.async_support`
  - KIS/키움: `httpx` 기반 커스텀 어댑터

## 프로젝트 구조

```text
tutong-v3/
├── backend/      # FastAPI API 서버
├── bot_engine/   # Celery 기반 봇 엔진
├── frontend/     # React SPA
├── docs/         # 기획/요구사항/아키텍처/DB/가이드 문서
├── compose.yml
└── compose.override.yml
```

## 빠른 시작 (Docker 권장)

사전 요구사항:
- Docker + Docker Compose

실행:

```bash
docker compose watch
```

주요 로컬 URL:
- Frontend: http://localhost:5173
- Backend API: http://localhost:8000
- Swagger: http://localhost:8000/docs
- Adminer: http://localhost:8080
- MailCatcher: http://localhost:1080
- Traefik Dashboard: http://localhost:8090

## 로컬 개발 명령

백엔드:

```bash
cd backend
uv sync
uv run fastapi dev app/main.py
uv run alembic upgrade head
uv run pytest
uv run prek run --all-files
```

봇 엔진:

```bash
cd bot_engine
uv sync
uv run celery -A celery_app worker --loglevel=info
```

프론트엔드:

```bash
cd frontend
bun install
bun run dev
```

OpenAPI 클라이언트 동기화 (백엔드 API 변경 후):

```bash
bash scripts/generate-client.sh
```

## 개발 원칙 (요약)

- 템플릿 기본 구조를 유지하고 필요한 영역만 확장
- SQLModel/CRUD/Router 패턴을 템플릿 스타일에 맞춰 작성
- 금융 계산은 `Decimal`만 사용 (`float` 계산 금지)
- 민감 정보(API Key/Secret) 로그 출력 금지
- API Key는 AES-256-GCM으로 암복호화

세부 규칙은 [CLAUDE.md](./CLAUDE.md), [docs/09_DEV_GUIDELINES.md](./docs/09_DEV_GUIDELINES.md) 참고.

## 문서 맵

- [프로젝트 문서 가이드](./docs/00_PROJECT_DOCUMENT_GUIDE.md)
- [프로젝트 기획안](./docs/01_PROJECT_PROPOSAL.md)
- [요구사항 명세서](./docs/02_REQUIREMENTS.md)
- [시스템 아키텍처 설계서](./docs/03_SYSTEM_ARCHITECTURE.md)
- [기술 스택 정의서](./docs/04_TECH_STACK.md)
- [UI/UX 설계서](./docs/05_UI_DESIGN_SPEC.md)
- [데이터베이스 설계서](./docs/07_DATABASE_DESIGN.md)
- [외부 API 연동 명세서](./docs/08_EXTERNAL_API_INTEGRATION.md)
- [개발 가이드라인](./docs/09_DEV_GUIDELINES.md)
- [WBS/개발 일정표](./docs/10_WBS_SCHEDULE.md)

## 현재 진행 상태 (문서 기준)

- Phase 1-1 (기반 기능): 완료
- Phase 1-2 (봇 엔진/전략): 5개 전략 + 자동 종료 로직 + 프론트 화면 고도화 완료
- Phase 1-3 (추가 연동/알림): 완료
- Phase 1-4 (QA/운영 정합): 진행 중

## 최근 반영 사항 (2026-03-12)

- 인증 경로를 화면정의서 기준으로 정합화:
  - `/auth/login`
  - `/auth/register`
  - `/auth/forgot-password`
- 로그인 화면 소셜 버튼(google/kakao) UI 반영(준비중 상태)
- 회원가입 필수 동의(이용약관/투자위험고지) 체크박스 반영
- 공통 상단 헤더에 알림(bell)/프로필 드롭다운 UI 반영
- 계좌 추가 플로우 개선:
  - `POST /api/v1/accounts/test-connection` 추가
  - 연결 테스트 성공 시에만 저장 가능하도록 프론트 반영
- 봇 상세 `최근 주문` 개선:
  - 로그 메시지 기반 표시 → 실제 체결 기반 매매내역 테이블로 전환
  - 표시 항목: 체결시간, 종목명, 매수/매도, 수량, 단가, 금액, 수수료, 주문시간

## 직전 반영 사항 (2026-03-07 ~ 2026-03-08)

- 봇 생성 상세 라우트 분리(`/bots/new/*`)
- 설정/빌링 상세 경로 분리(`/settings/*`, `/billing/*`)
- 대시보드 실데이터 기반 시각화 반영
- GitHub Actions 워크플로우 비활성화
