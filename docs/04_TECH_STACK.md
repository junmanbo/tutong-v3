# 기술 스택 정의서

**프로젝트명:** AutoTrade Platform  
**문서 버전:** v1.0  
**작성일:** 2025년  
**작성자:** PM / Tech Lead

---

## 목차

1. [기술 선택 원칙](#1-기술-선택-원칙)
2. [Frontend](#2-frontend)
3. [Backend API](#3-backend-api)
4. [Bot Engine](#4-bot-engine)
5. [데이터베이스 및 캐시](#5-데이터베이스-및-캐시)
6. [인프라 및 DevOps](#6-인프라-및-devops)
7. [모니터링 및 로깅](#7-모니터링-및-로깅)
8. [외부 서비스](#8-외부-서비스)
9. [개발 도구](#9-개발-도구)
10. [기술 스택 요약 다이어그램](#10-기술-스택-요약-다이어그램)
11. [변경 이력](#11-변경-이력)

---

## 1. 기술 선택 원칙

- **생산성:** 빠른 MVP 개발을 위해 검증된 프레임워크 우선 선택
- **확장성:** 사용자 증가 및 거래소 추가에 유연하게 대응 가능한 구조
- **생태계:** 활발한 커뮤니티와 라이브러리 지원
- **타입 안전성:** Pydantic 기반 런타임 타입 검증으로 데이터 안전성 확보
- **언어 통일 (Python):** Backend API와 Bot Engine을 모두 Python으로 통일하여 코드·라이브러리·어댑터 공유 극대화
- **금융 도메인 친화성:** Python의 풍부한 금융·데이터 분석 생태계 (numpy, pandas 등) 활용 가능, 추후 AI 전략 기능 확장에 유리
- **국내 서비스 호환:** 업비트, 한국투자증권 등 국내 API 연동 용이성

---

## 2. Frontend

> **템플릿 기반:** `fastapi/full-stack-fastapi-template`의 프론트엔드 구조를 그대로 사용합니다.

| 기술 | 버전 | 비고 |
|------|------|------|
| **Vite** | 최신 | 빌드 도구. 템플릿 기본 제공 |
| **React** | 18+ | 컴포넌트 기반 UI. 템플릿 기본 제공 |
| **TypeScript** | 5+ | 타입 안전성. 템플릿 기본 제공 |
| **Tailwind CSS** | 4+ | 빠른 UI 구현. 템플릿 기본 제공 |
| **shadcn/ui** | 최신 | 접근성 높은 UI 컴포넌트. 템플릿 기본 제공 |
| **TanStack Router** | 최신 | 파일 기반 라우팅. 템플릿 기본 제공 |
| **TanStack Query** | v5 | 서버 상태 관리, 캐싱. 템플릿 기본 제공 |
| **TanStack Table** | 최신 | 데이터 테이블 (봇 목록, 주문 내역 등). 템플릿 기본 제공 |
| **React Hook Form + Zod** | 최신 | 폼 검증. 템플릿 기본 제공 |
| **Biome** | 최신 | 린터 + 포매터 (프론트엔드 전용). 템플릿 기본 제공 |
| **Playwright** | 최신 | E2E 테스트. 템플릿 기본 제공 |
| **Recharts** | 최신 | 수익 차트, 포트폴리오 비중 차트 — **신규 추가** |
| **TradingView Lightweight Charts** | 최신 | 캔들 차트, 그리드 레벨 시각화 — **신규 추가** |

### OpenAPI 클라이언트 자동 생성

템플릿의 핵심 기능 중 하나입니다. 백엔드 FastAPI 스키마로부터 프론트엔드 타입과 API 호출 함수를 자동 생성합니다.

```bash
# 백엔드 OpenAPI 스펙 추출 → 프론트엔드 클라이언트 코드 자동 생성
bash scripts/generate-client.sh
```

생성 결과: `frontend/src/client/` 디렉토리에 `types.gen.ts`, `sdk.gen.ts` 자동 생성.  
백엔드 API 변경 시 이 스크립트를 다시 실행하면 프론트엔드 타입이 자동 동기화됩니다.

### 차트 라이브러리 결정

| 라이브러리 | 용도 |
|-----------|------|
| **Recharts** | 수익 차트, 포트폴리오 비중 차트 (간단한 차트) |
| **TradingView Lightweight Charts** | 캔들 차트, 그리드 레벨 시각화 (금융 차트) |

---

## 3. Backend API

> **템플릿 기반:** `fastapi/full-stack-fastapi-template`의 백엔드 구조를 기반으로 확장합니다.

| 기술 | 버전 | 비고 |
|------|------|------|
| **Python** | 3.12+ | 템플릿 기본 제공 |
| **FastAPI** | 0.115+ | 템플릿 기본 제공 |
| **SQLModel** | 0.0.21+ | ORM + Pydantic 통합 라이브러리. 템플릿 기본 제공 |
| **Alembic** | 최신 | DB 마이그레이션. 템플릿 기본 제공 |
| **psycopg** | 3+ | PostgreSQL 드라이버 (동기). 템플릿 기본 제공 |
| **Pydantic v2** | 2+ | 스키마 검증. 템플릿 기본 제공 |
| **pydantic-settings** | 2+ | 환경변수 관리. 템플릿 기본 제공 |
| **PyJWT** | 2+ | JWT 토큰 발급·검증. 템플릿 기본 제공 |
| **pwdlib (argon2 + bcrypt)** | 최신 | 비밀번호 해싱. 템플릿 기본 제공 |
| **tenacity** | 최신 | 재시도 로직. 템플릿 기본 제공 |
| **httpx** | 최신 | KIS·키움 REST API 호출 (CCXT 미지원 거래소). 템플릿 기본 제공 |
| **Sentry SDK** | 최신 | 에러 트래킹. 템플릿 기본 제공 |
| **Celery** | 5+ | 분산 작업 큐 — 봇 명령 비동기 처리 — **신규 추가** |
| **CCXT** | 최신 | Binance·Upbit 거래소 API 통합 래퍼 — **신규 추가** |
| **uvicorn** | 최신 | ASGI 서버. 템플릿 기본 제공 |
| **uv** | 최신 | 패키지 관리자. 템플릿 기본 제공 |

### SQLModel 채택 배경

템플릿이 SQLAlchemy 위에 Pydantic을 통합한 **SQLModel**을 사용합니다. ORM 모델과 Pydantic 스키마를 하나의 클래스로 정의해 중복을 줄입니다.

```python
# SQLModel 방식 — ORM 모델과 API 스키마를 하나의 클래스 계층으로 관리
class UserBase(SQLModel):              # 공통 필드
    email: str
    full_name: str | None = None

class User(UserBase, table=True):      # DB 테이블 (ORM)
    id: UUID = Field(default_factory=uuid4, primary_key=True)
    hashed_password: str

class UserPublic(UserBase):            # API 응답 스키마
    id: UUID

class UserCreate(UserBase):            # API 요청 스키마
    password: str
```

> 봇 설정 등 템플릿에 없는 복잡한 테이블은 동일한 SQLModel 패턴으로 추가 작성합니다.

---

## 4. Bot Engine

| 기술 | 버전 | 선택 이유 |
|------|------|-----------|
| **Python** | 3.12+ | API 서버와 언어 통일 — 어댑터·모델·유틸리티 패키지 직접 공유 |
| **Celery** | 5+ | 분산 Worker 기반 봇 명령 처리, Redis Broker 연동 |
| **CCXT** | 최신 | Binance·Upbit REST + WebSocket 통합 래퍼. 서명·Rate Limit·심볼 정규화 자동 처리 — **신규 추가** |
| **APScheduler** | 3.x+ | DCA·Rebalancing 주기적 스케줄링 (AsyncIOScheduler) |
| **decimal (내장)** | Python 표준 | 금융 계산 부동소수점 오류 방지 |
| **httpx** | 최신 | KIS·키움증권 REST API 호출 (CCXT 미지원 거래소) |

### 거래소별 구현 방식

| 거래소 | 구현 방식 | CCXT 클래스 | 이유 |
|--------|-----------|------------|------|
| **Binance** | **CCXT** | `ccxt.async_support.binance` | REST + `watch_*` WebSocket 완전 지원 |
| **Upbit** | **CCXT** | `ccxt.async_support.upbit` | REST + WebSocket 지원, 업비트 공식 CCXT 가이드 제공 |
| **한국투자증권 (KIS)** | **직접 구현 (httpx)** | — | CCXT 미지원, OAuth 2.0 + tr_id 커스텀 헤더 구조 |
| **키움증권** | **직접 구현 (httpx)** | — | CCXT 미지원, App Key/Secret 커스텀 인증 구조 |

> ⚠️ **부동소수점 주의:** CCXT가 반환하는 가격·수량은 Python `float`입니다. 반드시 `Decimal(str(value))`로 변환 후 계산하세요. `Decimal(float_value)` 직접 변환은 정밀도 오류가 발생합니다.

---

## 5. 데이터베이스 및 캐시

| 기술 | 용도 | 선택 이유 |
|------|------|-----------|
| **PostgreSQL** | 메인 데이터베이스 | ACID 트랜잭션, JSON 지원, 강력한 쿼리 |
| **Redis** | 캐시 / 세션 / 큐 | 인메모리 고속 처리, Celery Broker 및 Result Backend |
| **TimescaleDB** | 시계열 데이터 (선택) | 가격 데이터, 수익 이력 시계열 최적화 저장 |

### 주요 테이블 목록 (상세는 DB 설계서 참조)

- `users` — 사용자 계정
- `exchange_accounts` — 거래소 연동 계좌 (API Key 암호화 저장)
- `bots` — 봇 정보 및 설정
- `bot_orders` — 봇이 발행한 주문 내역
- `bot_trades` — 봇 체결 내역
- `bot_logs` — 봇 실행 로그
- `subscriptions` — 구독 정보
- `notifications` — 알림 발송 내역

---

## 6. 인프라 및 DevOps

> **배포 전략:** On-premise(홈서버) 우선 운영 → 사용자 증가 시 클라우드(AWS) 단계적 전환.
> Docker 컨테이너로 운영하므로 이미지 재사용으로 전환 비용 최소화.

### Phase 1 — On-premise 핵심 기술

| 기술 | 용도 |
|------|------|
| **Docker** | 컨테이너화 — 개발·운영 환경 동일 보장 |
| **Docker Compose** | 전체 서비스 통합 실행 (개발 + 운영 공통) |
| **Nginx** | Reverse Proxy, HTTPS 종료, 정적 파일 서빙 |
| **Certbot (Let's Encrypt)** | 무료 SSL/TLS 인증서 발급 및 자동 갱신 |
| **DDNS** | 유동 IP 환경에서 도메인 연결 (DuckDNS / Cloudflare) |
| **Prometheus + Grafana** | 시스템·서비스 메트릭 자가 호스팅 모니터링 |
| **Loki** | 로그 수집 및 조회 (Grafana와 통합) |
| **GitHub Actions** | CI/CD — 테스트 자동화, 서버 배포 자동화 |
| **pg_dump + cron** | PostgreSQL 정기 자동 백업 |

### Phase 2 — 클라우드 전환 (AWS)

사용자 규모가 커지거나 고가용성이 필요할 때 전환합니다. Docker 이미지를 그대로 사용합니다.

| 기술 | 용도 | Phase 1 대응 |
|------|------|-------------|
| **AWS ECS (Fargate)** | 서버리스 컨테이너 오케스트레이션 | Docker Compose |
| **AWS RDS PostgreSQL** | 관리형 DB (자동 백업, 멀티AZ) | PostgreSQL 컨테이너 |
| **AWS ElastiCache Redis** | 관리형 Redis | Redis 컨테이너 |
| **AWS S3 + CloudFront** | 프론트엔드 CDN 배포 | Nginx 정적 파일 서빙 |
| **AWS Secrets Manager** | 시크릿 안전 보관 | `.env` 파일 (서버 로컬) |
| **AWS CloudWatch** | 로그·메트릭 통합 관리 | Prometheus + Loki |
| **Terraform** | 인프라 as Code | — |

### Docker Compose 서비스 구성

```yaml
# compose.yml (개발 + 운영 공통 기반 — 템플릿 기반 + 추가)
services:
  # ── 템플릿 기본 제공 ─────────────────────────────────
  db:          # PostgreSQL 18
  backend:     # FastAPI API 서버
  frontend:    # Vite React SPA
  adminer:     # DB 관리 UI (개발용)
  mailcatcher: # 이메일 테스트 (개발용)
  proxy:       # Traefik (개발용 라우팅)

  # ── 신규 추가 ─────────────────────────────────────────
  redis:       # Redis (Celery Broker)
  bot_engine:  # Celery Worker (봇 엔진)

# compose.prod.yml (운영 오버라이드)
# - adminer, mailcatcher 제거
# - Traefik → Nginx로 교체
# - 볼륨 마운트 경로 지정 (DB 데이터 영속화)
```

---

## 7. 모니터링 및 로깅

| 기술 | 용도 | 단계 |
|------|------|------|
| **Prometheus** | 서비스 메트릭 수집 (응답시간, 오류율 등) | Phase 1 (자가 호스팅) |
| **Grafana** | 메트릭·로그 통합 대시보드 | Phase 1 (자가 호스팅) |
| **Loki** | 구조화 로그 수집 (Grafana와 연동) | Phase 1 (자가 호스팅) |
| **Sentry** | 에러 트래킹 (프론트/백엔드) — 무료 티어 | Phase 1~2 공통 |
| **AWS CloudWatch** | 로그·메트릭 통합 (클라우드 전환 시) | Phase 2 (AWS) |

---

## 8. 외부 서비스

| 서비스 | 용도 | 비고 |
|--------|------|------|
| **Gmail SMTP** | 이메일 발송 — App Password 사용 | Phase 1 무료 |
| **SendGrid** | 이메일 발송 대안 (월 100건 무료 티어) | Phase 1 가능 |
| **AWS SES** | 이메일 발송 (대량 발송 시) | Phase 2 전환 시 |
| **Telegram Bot API** | Telegram 알림 (Phase 2) | |
| **토스페이먼츠 / 아임포트** | 국내 카드 결제 PG 연동 | |
| **Google OAuth / Kakao OAuth** | 소셜 로그인 | |

---

## 9. 개발 도구

| 도구 | 용도 | 비고 |
|------|------|------|
| **uv** | Python 패키지 관리자 | 템플릿 기본 제공 |
| **Ruff** | Python 린터 + 포매터 | 템플릿 기본 제공 |
| **mypy** | Python 정적 타입 검사 | 템플릿 기본 제공 |
| **pytest** | 백엔드 단위/통합 테스트 | 템플릿 기본 제공 |
| **Biome** | 프론트엔드 린터 + 포매터 | 템플릿 기본 제공 (ESLint 대체) |
| **Playwright** | E2E 테스트 (Frontend) | 템플릿 기본 제공 |
| **pre-commit** | 커밋 전 Ruff·mypy 자동 실행 | 템플릿 기본 제공 |
| **Adminer** | 로컬 DB 관리 UI | 템플릿 기본 제공 |
| **Mailcatcher** | 로컬 이메일 수신 테스트 | 템플릿 기본 제공 |
| **Sentry** | 에러 트래킹 (프론트/백엔드) | 템플릿 기본 제공 |
| **VS Code** | 주 IDE | |
| **GitHub** | 소스 코드 버전 관리 | |

---

## 10. 기술 스택 요약 다이어그램

```
┌─────────────────────────────────────────────────────────┐
│  FRONTEND  [템플릿 기반 + 차트 추가]                       │
│  Vite + React 18 + TypeScript + Tailwind CSS            │
│  TanStack Router | TanStack Query | shadcn/ui           │
│  Recharts | TradingView Lightweight Charts (추가)        │
│  OpenAPI 클라이언트 자동생성 (generate-client.sh)          │
└─────────────────────────────────────────────────────────┘
                          │
┌─────────────────────────────────────────────────────────┐
│  BACKEND API  [템플릿 기반 + 봇/거래소 기능 추가]           │
│  FastAPI (Python 3.12) + SQLModel + Pydantic v2         │
│  JWT Auth | Celery (추가) | OpenAPI 자동 생성             │
│  uv (패키지 관리)                                         │
└─────────────────────────────────────────────────────────┘
                          │
┌─────────────────────────────────────────────────────────┐
│  BOT ENGINE  [신규 추가]                                  │
│  Python 3.12 + Celery Workers                          │
│  CCXT (Binance/Upbit) | httpx (KIS/Kiwoom)            │
│  decimal | APScheduler                                 │
└─────────────────────────────────────────────────────────┘
                          │
┌──────────┐  ┌──────────┐  ┌────────────────────────────┐
│PostgreSQL│  │  Redis   │  │  Exchange Adapters (추가)   │
│(Main DB) │  │(Celery Q)│  │  Binance | Upbit | KIS     │
└──────────┘  └──────────┘  │  Kiwoom REST API           │
                             └────────────────────────────┘
                          │
┌─────────────────────────────────────────────────────────┐
│  INFRASTRUCTURE                                         │
│  Phase 1: 홈서버 + Docker Compose + Nginx + Certbot     │
│           Prometheus + Grafana + Loki (자가 호스팅)       │
│  Phase 2: AWS ECS | RDS | ElastiCache | CloudFront     │
│           (사용자 증가 시 전환 — Docker 이미지 재사용)       │
└─────────────────────────────────────────────────────────┘
```

---

## 11. 변경 이력

| 버전 | 날짜 | 변경 내용 | 작성자 |
|------|------|-----------|--------|
| v1.0 | 2025년 | 최초 작성 | PM |
| v1.1 | 2025년 | 키움증권 연동 방식 변경 반영 — Windows 브릿지 서버 제거, 키움 REST API 직접 연동 | PM |
| v1.2 | 2025년 | Backend API 및 Bot Engine 기술 스택 전면 변경 — NestJS(Node.js/TS) → FastAPI(Python). 연쇄 변경: Prisma→SQLAlchemy+Alembic, Passport.js→python-jose, class-validator→Pydantic, BullMQ→Celery, node-cron→APScheduler, Decimal.js→decimal(내장), Jest→pytest, Winston→structlog, ESLint/Prettier/Husky→Ruff/mypy/pre-commit | PM |
| v1.3 | 2025년 | fastapi/full-stack-fastapi-template 기반으로 개발 방식 전환. Frontend: Next.js → Vite+React+TanStack Router. Backend ORM: SQLAlchemy(async) → SQLModel(동기). 추가: OpenAPI 클라이언트 자동생성, Biome, pwdlib, Mailcatcher, Adminer, Traefik. 제거: Zustand, Axios, Socket.io-client, pytest-asyncio | PM |
| v1.4 | 2025년 | 인프라 전략 변경 — AWS 단독 구성 → On-premise 우선 + 클라우드 단계적 전환. Phase 1: Docker Compose + Nginx + Certbot + Prometheus/Grafana/Loki. Phase 2: AWS ECS/RDS/ElastiCache. 이메일: AWS SES → Gmail SMTP / SendGrid 무료 티어 우선 | PM |
| v1.5 | 2025년 | Binance·Upbit 거래소 연동 방식 변경 — 직접 REST/WebSocket 구현 → CCXT 라이브러리(`ccxt.async_support`) 사용. httpx 용도를 KIS·키움 전용으로 변경. Bot Engine 기술 스택에 CCXT 추가, websockets 제거. 거래소별 구현 방식 테이블 추가 | PM |

---

*기술 스택은 팀 역량 및 프로젝트 상황에 따라 조정될 수 있습니다.*
