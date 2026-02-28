# 시스템 아키텍처 설계서

**프로젝트명:** AutoTrade Platform  
**문서 버전:** v1.0  
**작성일:** 2025년  
**작성자:** PM / 아키텍트

---

## 목차

1. [아키텍처 개요](#1-아키텍처-개요)
2. [시스템 구성도](#2-시스템-구성도)
3. [레이어 아키텍처](#3-레이어-아키텍처)
4. [봇 엔진 설계](#4-봇-엔진-설계)
5. [거래소 연동 아키텍처 (어댑터 패턴)](#5-거래소-연동-아키텍처)
6. [데이터 흐름도](#6-데이터-흐름도)
7. [인프라 구성](#7-인프라-구성)
8. [보안 아키텍처](#8-보안-아키텍처)
9. [변경 이력](#9-변경-이력)

---

## 1. 아키텍처 개요

AutoTrade Platform은 아래의 핵심 원칙을 기반으로 설계합니다.

| 원칙 | 내용 |
|------|------|
| **분리된 봇 엔진** | 봇 실행 엔진은 웹 서버와 독립적으로 운영 (서버 재시작 시에도 봇 지속 실행) |
| **어댑터 패턴** | 거래소 추가 시 어댑터 하나만 구현하면 기존 봇 전략 그대로 활용 가능 |
| **비동기 메시지 처리** | 봇 명령(시작/중지)은 메시지 큐를 통해 비동기 처리 |
| **이벤트 기반** | 거래소 WebSocket으로 실시간 가격 수신, 봇 로직 트리거 |

---

## 2. 시스템 구성도

```
┌────────────────────────────────────────────────────────────────┐
│                         사용자 (Browser)                          │
└────────────────────────────┬────────────────────────────────────┘
                             │ HTTPS
┌────────────────────────────▼────────────────────────────────────┐
│                    CDN / Load Balancer                           │
└────────┬──────────────────────────────────────┬─────────────────┘
         │                                      │
┌────────▼──────────┐                 ┌─────────▼─────────┐
│   Frontend (Web)   │                 │  Backend API Server │
│   Vite + React     │ ◄──── REST ────►│  FastAPI (Python)  │
│   (TanStack Router)│                 │  uvicorn            │
└────────────────────┘                 └─────────┬──────────┘
                                                 │
                               ┌─────────────────┼──────────────────┐
                               │                 │                  │
                    ┌──────────▼─────┐  ┌────────▼───────┐  ┌──────▼──────┐
                    │  Message Queue  │  │   PostgreSQL   │  │    Redis    │
                    │  (Redis/RabbitMQ│  │   (Main DB)    │  │  (Cache /   │
                    │   /SQS)         │  │                │  │   Session)  │
                    └──────────┬──────┘  └────────────────┘  └─────────────┘
                               │
                    ┌──────────▼──────────────────────────┐
                    │           Bot Engine Workers          │
                    │   (독립 실행 프로세스 / 컨테이너)          │
                    │                                      │
                    │  ┌──────────┐  ┌───────────────┐    │
                    │  │ SpotGrid │  │ PositionSnow  │    │
                    │  │ Worker   │  │    Worker     │    │
                    │  └──────────┘  └───────────────┘    │
                    │  ┌──────────┐  ┌───────────────┐    │
                    │  │ Rebal    │  │   DCA Worker  │    │
                    │  │ Worker   │  │               │    │
                    │  └──────────┘  └───────────────┘    │
                    │  ┌──────────────────────────────┐   │
                    │  │       Algo Orders Worker      │   │
                    │  └──────────────────────────────┘   │
                    └──────────┬──────────────────────────┘
                               │
         ┌─────────────────────┼──────────────────────┐
         │                     │                       │
┌────────▼────────┐  ┌─────────▼────────┐  ┌──────────▼──────────┐  ┌──────────────────────┐
│ Binance Adapter │  │ Upbit Adapter    │  │  KIS Adapter        │  │  Kiwoom Adapter      │
│ REST + WS       │  │ REST + WS        │  │  REST + WS          │  │  REST + WS           │
└────────┬────────┘  └─────────┬────────┘  └──────────┬──────────┘  └──────────┬───────────┘
         │                     │                       │                        │
┌────────▼────────┐  ┌─────────▼────────┐  ┌──────────▼──────────┐  ┌──────────▼───────────┐
│  Binance        │  │  Upbit           │  │  한국투자증권          │  │  키움증권             │
│  Exchange       │  │  Exchange        │  │  KIS API            │  │  Kiwoom REST API     │
└─────────────────┘  └──────────────────┘  └─────────────────────┘  └──────────────────────┘

---

## 3. 레이어 아키텍처

### 3.1 Frontend (Vite + React — 템플릿 기반)

템플릿이 제공하는 구조를 그대로 사용하며, 봇/거래소 관련 라우트와 컴포넌트를 추가합니다.

```
frontend/src/
├── client/                 # [템플릿] OpenAPI 자동생성 클라이언트
│   ├── types.gen.ts        #   백엔드 스키마 → TS 타입 (자동생성)
│   └── sdk.gen.ts          #   API 호출 함수 (자동생성)
├── routes/                 # [템플릿] TanStack Router 파일 기반 라우팅
│   ├── __root.tsx          #   루트 레이아웃
│   ├── _layout.tsx         #   인증 후 공통 레이아웃 (사이드바 포함)
│   ├── _layout/
│   │   ├── index.tsx       #   [템플릿] 대시보드 홈
│   │   ├── admin.tsx       #   [템플릿] 관리자 (슈퍼유저 전용)
│   │   ├── settings.tsx    #   [템플릿] 사용자 설정
│   │   ├── bots.tsx        #   [추가] 봇 목록/관리 페이지
│   │   ├── bots.$botId.tsx #   [추가] 봇 상세/모니터링 페이지
│   │   └── accounts.tsx    #   [추가] 거래소 계좌 연동 페이지
│   ├── login.tsx           #   [템플릿] 로그인 페이지
│   └── signup.tsx          #   [템플릿] 회원가입 페이지
├── components/
│   ├── ui/                 # [템플릿] shadcn/ui 공통 컴포넌트
│   ├── Common/             # [템플릿] 공통 레이아웃 컴포넌트
│   ├── Admin/              # [템플릿] 관리자 컴포넌트
│   ├── UserSettings/       # [템플릿] 사용자 설정 컴포넌트
│   ├── Bots/               # [추가] 봇 관련 컴포넌트
│   └── Charts/             # [추가] 차트 컴포넌트 (Recharts, TradingView)
├── hooks/
│   ├── useAuth.ts          # [템플릿] 인증 훅
│   └── useBots.ts          # [추가] 봇 상태 관련 훅
└── utils.ts                # [템플릿] 공통 유틸리티
```

### 3.2 Backend API (FastAPI — 템플릿 기반)

템플릿의 구조를 그대로 유지하며, 봇/거래소 관련 라우터와 모델을 추가합니다.

```
backend/app/
├── api/
│   ├── main.py             # [템플릿] api_router 통합 진입점
│   ├── deps.py             # [템플릿] 공통 의존성 (DB세션, 현재사용자)
│   └── routes/
│       ├── login.py        # [템플릿] 로그인, 비밀번호 재설정
│       ├── users.py        # [템플릿] 사용자 CRUD, 회원가입
│       ├── utils.py        # [템플릿] 헬스체크
│       ├── private.py      # [템플릿] 개발용 (local 환경만)
│       ├── accounts.py     # [추가] 거래소 계좌 연동 CRUD
│       ├── bots.py         # [추가] 봇 CRUD 및 시작/중지
│       ├── dashboard.py    # [추가] 대시보드 집계 데이터
│       ├── notifications.py# [추가] 알림 설정
│       └── billing.py      # [추가] 구독/결제
├── core/
│   ├── config.py           # [템플릿] 환경 설정 (pydantic-settings)
│   ├── security.py         # [템플릿] JWT, 비밀번호 해싱 (pwdlib)
│   └── db.py               # [템플릿] DB 엔진, init_db
├── models.py               # [템플릿] User, Item SQLModel 정의
│                           #          → 봇 관련 모델 이 파일에 추가 또는
│                           #            models/ 디렉토리로 분리 확장
├── crud.py                 # [템플릿] User CRUD 함수
│                           #          → Bot, Account CRUD 추가
├── exchange_adapters/      # [추가] 거래소 어댑터
│   ├── base.py             #   AbstractExchangeAdapter (ABC)
│   ├── binance.py
│   ├── upbit.py
│   ├── kis.py
│   └── kiwoom.py
├── utils.py                # [템플릿] 이메일 발송 유틸
├── email-templates/        # [템플릿] 이메일 HTML 템플릿
├── initial_data.py         # [템플릿] 초기 슈퍼유저 생성
└── main.py                 # [템플릿] FastAPI 앱 진입점
```

### 3.3 Bot Engine (독립 서비스 — 신규 추가)

```
bot_engine/
├── workers/
│   ├── spot_grid.py        # Celery Task — Spot Grid 봇 워커
│   ├── position_snowball.py# Celery Task — Position Snowball 워커
│   ├── rebalancing.py      # Celery Task — Rebalancing 봇 워커
│   ├── spot_dca.py         # Celery Task — Spot DCA 워커
│   └── algo_orders.py      # Celery Task — Algo Orders 워커
├── strategies/             # 봇 전략 핵심 로직 (순수 Python)
├── scheduler.py            # APScheduler — DCA·Rebalancing 주기 실행
└── celery_app.py           # Celery 앱 설정 (Broker: Redis)
```

> **거래소 어댑터 공유 방식:** Bot Engine은 `backend/app/exchange_adapters/`를 직접 참조하지 않습니다. `backend` 패키지를 `uv` workspace로 공유하거나, 어댑터를 별도 `exchange_adapters/` 패키지로 분리해 두 서비스에서 설치합니다. 구체적인 방식은 개발 초기에 확정합니다.

---

## 4. 봇 엔진 설계

### 4.1 봇 생명주기

```
[생성 (CREATED)]
      │
      ▼
[설정 완료 (CONFIGURED)]
      │
      ▼ (시작 명령)
[대기 (PENDING)] ──── 큐에 메시지 전달 ────►
      │                                  Bot Engine Worker
      ▼                                  수신 및 실행 시작
[실행 중 (RUNNING)]
      │
      ├── 정상 종료 (목표 달성) ──────────► [완료 (COMPLETED)]
      ├── 사용자 중지 ────────────────────► [중지됨 (STOPPED)]
      ├── 오류 발생 ──────────────────────► [오류 (ERROR)]
      └── 손절 한도 도달 ─────────────────► [손절 종료 (STOPPED_BY_SL)]
```

### 4.2 봇 명령 흐름 (메시지 큐 기반)

```
사용자 → API 서버 → [Bot Command Queue] → Bot Engine Worker
                                              │
                                              ▼
                                       거래소 어댑터 호출
                                              │
                                              ▼
                                       주문 결과 수신
                                              │
                                              ▼
                                       DB 저장 + 알림 발송
```

### 4.3 실시간 가격 수신 (WebSocket)

```
거래소 WebSocket ──► Price Stream ──► 봇 전략 조건 체크
                                              │
                                      [조건 충족 시]
                                              │
                                              ▼
                                       주문 실행 큐에 Push
```

---

## 5. 거래소 연동 아키텍처

### 5.1 Exchange Adapter 인터페이스

모든 거래소 어댑터는 아래 공통 인터페이스를 구현합니다.

```python
from abc import ABC, abstractmethod
from decimal import Decimal
from typing import AsyncGenerator

class AbstractExchangeAdapter(ABC):
    # 계좌 정보
    @abstractmethod
    async def get_balance(self) -> list[Balance]: ...

    # 주문
    @abstractmethod
    async def place_order(self, order: OrderRequest) -> OrderResponse: ...

    @abstractmethod
    async def cancel_order(self, order_id: str) -> None: ...

    @abstractmethod
    async def get_order_status(self, order_id: str) -> OrderStatus: ...

    # 시세
    @abstractmethod
    async def get_current_price(self, symbol: str) -> Decimal: ...

    @abstractmethod
    async def get_order_book(self, symbol: str) -> OrderBook: ...

    # 스트리밍 (asyncio 기반 async generator)
    @abstractmethod
    async def price_stream(self, symbol: str) -> AsyncGenerator[PriceTick, None]: ...

    # 거래 내역
    @abstractmethod
    async def get_trade_history(self, params: TradeHistoryParams) -> list[Trade]: ...
```

### 5.2 키움증권 REST API Adapter

키움증권은 2025년 **키움 REST API**(https://openapi.kiwoom.com)를 공식 출시했습니다. 기존 Windows COM(OCX) 기반 OpenAPI+와 달리 표준 HTTP REST + WebSocket 방식을 지원하므로, 별도 브릿지 서버 없이 Linux 서버 환경에서 다른 거래소 어댑터와 동일한 구조로 직접 연동합니다.

```
[Bot Engine / API Server]  ← Linux/Docker 컨테이너
         │
         │ HTTPS REST 요청 (App Key / Secret Key 인증)
         │ + WebSocket (실시간 체결·시세)
         ▼
[키움 REST API 서버]  ← openapi.kiwoom.com
         │
         ▼
[키움증권 매매 시스템]
```

**연동 시 주요 고려사항:**

| 항목 | 내용 |
|------|------|
| 인증 방식 | App Key + Secret Key → 토큰 발급 후 API 호출 |
| IP 화이트리스트 | 키움 REST API 포털에서 허용 IP 사전 등록 필요 (미등록 시 호출 차단) |
| 실시간 시세 | WebSocket으로 주식 현재가·호가·체결 데이터 수신 |
| 모의투자 | 별도 모의투자 서버 제공 — 개발·테스트 단계에서 활용 권장 |
| 공식 포털 | https://openapi.kiwoom.com |

---

## 6. 데이터 흐름도

### 6.1 봇 설정 및 시작 흐름

```
1. 사용자 → 봇 설정 입력 → API 서버
2. API 서버 → 설정 유효성 검증
3. API 서버 → DB에 봇 정보 저장 (상태: PENDING)
4. API 서버 → Message Queue에 "BOT_START" 이벤트 발행
5. Bot Engine → Queue 수신 → 거래소 WebSocket 연결
6. Bot Engine → 봇 전략 루프 시작
7. Bot Engine → DB 봇 상태 업데이트 (RUNNING)
8. Bot Engine → API 서버 → 사용자에게 알림 발송
```

### 6.2 주문 실행 흐름 (Spot Grid 예시)

```
1. 가격 스트림 수신: BTC/USDT = $65,000
2. 그리드 조건 체크: 하한가 도달 → 매수 조건 충족
3. 주문 요청 생성: { side: BUY, amount: 100 USDT, type: LIMIT }
4. 거래소 어댑터 → 바이낸스 REST API 주문 발행
5. 주문 체결 이벤트 수신 (WebSocket)
6. DB 거래 내역 저장
7. 봇 상태 업데이트 (총 수익, 포지션 등)
8. (옵션) 알림 발송
```

---

## 7. 인프라 구성

> **배포 전략:** 초기에는 집 서버(On-premise)로 서비스하고, 사용자 증가 시 클라우드로 단계적 전환합니다.
> 이를 위해 모든 서비스는 Docker 컨테이너로 운영하여 이식성을 보장합니다.

### 7.1 Phase 1 — On-premise (홈서버)

초기 MVP 및 베타 서비스 단계. 집 서버 한 대 또는 소수의 서버로 모든 컴포넌트를 운영합니다.

```
인터넷
    │ HTTPS (443)
    ▼
[공유기 포트포워딩 또는 DDNS]
    │
    ▼
┌──────────────────────────────────────────────────────┐
│                  홈서버 (Ubuntu Linux)                  │
│                                                      │
│  [Nginx]  ── Reverse Proxy + SSL (Let's Encrypt)    │
│     │                                               │
│     ├──► [Frontend Container]    (Vite React SPA)  │
│     └──► [Backend Container]     (FastAPI)         │
│                                                      │
│  [Bot Engine Container]  (Celery Worker)            │
│  [PostgreSQL Container]  (메인 DB, 볼륨 마운트)       │
│  [Redis Container]       (Celery Broker + 캐시)     │
│                                                      │
│  [Prometheus + Grafana]  (메트릭 모니터링)             │
│  [Loki]                  (로그 수집)                  │
└──────────────────────────────────────────────────────┘
    │
    ▼
거래소 API (Binance, Upbit, KIS, Kiwoom)
```

**권장 홈서버 최소 사양:**

| 항목 | 권장 사양 |
|------|-----------|
| CPU | 4코어 이상 (Intel/AMD x86-64) |
| RAM | 8GB 이상 (16GB 권장) |
| Storage | SSD 100GB 이상 (DB 볼륨 포함) |
| OS | Ubuntu 22.04 LTS / 24.04 LTS |
| 네트워크 | 유선 인터넷, 고정 IP 또는 DDNS |

**On-premise 핵심 구성 요소:**

| 컴포넌트 | 기술 | 비고 |
|----------|------|------|
| Reverse Proxy + SSL | Nginx + Certbot (Let's Encrypt) | 무료 SSL 자동 갱신 |
| 컨테이너 런타임 | Docker + Docker Compose | 모든 서비스 컨테이너화 |
| DB 백업 | pg_dump + 스크립트 (cron) | 외장하드 또는 원격지 백업 |
| 시크릿 관리 | `.env` 파일 (서버 로컬 저장) | 파일 권한 600, Git 커밋 금지 |
| 모니터링 | Prometheus + Grafana | 자가 호스팅 |
| 로그 수집 | Loki + Grafana | 자가 호스팅 |
| 이메일 발송 | SMTP (Gmail App Password 또는 SendGrid 무료 티어) | |

**DDNS 설정 (고정 IP 없는 경우):**

```bash
# 옵션 1: 무료 DDNS 서비스 (DuckDNS, No-IP 등)
# DuckDNS cron 예시 (5분마다 IP 갱신)
*/5 * * * * curl -s "https://www.duckdns.org/update?domains=MY_DOMAIN&token=MY_TOKEN&ip="

# 옵션 2: Cloudflare DDNS (도메인 보유 시)
# cloudflare-ddns 컨테이너 사용
```

**pg_dump 자동 백업 스크립트 예시:**

```bash
# /home/ubuntu/backup-db.sh
#!/bin/bash
DATE=$(date +%Y%m%d_%H%M%S)
docker exec autotrade-db pg_dump -U postgres autotrade > /mnt/backup/db_$DATE.sql
# 7일 이상 된 백업 자동 삭제
find /mnt/backup -name "db_*.sql" -mtime +7 -delete
```

### 7.2 Phase 2 — 클라우드 전환 (사용자 증가 시)

사용자가 일정 수준(예: 유료 구독 50명 이상, 동시 봇 200개 이상) 이상으로 증가하거나
서버 안정성·확장성이 필요해질 때 클라우드로 전환합니다.

**전환 용이성을 위해 Phase 1부터 Docker로 운영합니다.** 이미지를 ECR에 올리고
ECS Task Definition만 작성하면 전환 완료입니다.

| 컴포넌트 | On-premise (Phase 1) | AWS (Phase 2) |
|----------|---------------------|---------------|
| Frontend | Nginx (컨테이너) | S3 + CloudFront |
| Backend API | Docker Compose | ECS Fargate |
| Bot Engine | Docker Compose | ECS Fargate |
| Database | PostgreSQL 컨테이너 | RDS PostgreSQL |
| Cache | Redis 컨테이너 | ElastiCache Redis |
| SSL | Certbot (Let's Encrypt) | ACM (자동 관리) |
| 시크릿 | `.env` 파일 | Secrets Manager |
| 모니터링 | Prometheus + Grafana | CloudWatch |
| 로그 | Loki | CloudWatch Logs |
| IaC | Docker Compose | Terraform |

> ℹ️ 키움증권 REST API는 표준 HTTPS 방식이므로 On-premise·클라우드 어느 환경에서도 별도 Windows 서버 없이 직접 호출 가능합니다.

### 7.3 환경 구성

| 환경 | 목적 | 구성 |
|------|------|------|
| `development` | 로컬 개발 | Docker Compose (템플릿 기본) |
| `production` | 실서비스 운영 | On-premise 홈서버 (Phase 1) → 클라우드 (Phase 2) |

---

## 8. 보안 아키텍처

### 8.1 API Key 보안

```
사용자 입력 API Key
       │
       ▼
[암호화 처리 (AES-256-GCM)]
       │
       ▼
[DB 암호화 컬럼 저장 (BYTEA)]
(Phase 2 전환 시: AWS Secrets Manager로 마이그레이션 가능)
       │
       ▼
[Bot Engine만 복호화 권한 보유]
       │
       ▼
거래소 API 호출 시 복호화하여 사용 (메모리 내에서만 평문)
```

### 8.2 네트워크 보안

**Phase 1 — On-premise:**
```
인터넷
    │ HTTPS (443) — Let's Encrypt SSL
    ▼
[Nginx Reverse Proxy]
    │  ← 외부에서 직접 접근 불가
    ├──► Backend API (내부 포트 8000)
    └──► Frontend   (내부 포트 5173)

PostgreSQL / Redis / Bot Engine
    └── 외부 포트 미노출 (docker network 내부 통신만)
```

**Phase 2 — AWS:**
```
인터넷 → WAF → ALB → API Server (Private Subnet)
                   → Bot Engine (Private Subnet)
                   → DB (Private Subnet, 외부 접근 불가)
```

### 8.3 인증 흐름

```
로그인 요청
    │
    ▼
비밀번호 bcrypt 검증
    │
    ▼
Access Token (JWT, 1시간) + Refresh Token (14일) 발급
    │
    ▼
API 요청 시 Authorization: Bearer {access_token} 헤더 포함
    │
    ▼
만료 시 Refresh Token으로 갱신
```

---

## 9. 변경 이력

| 버전 | 날짜 | 변경 내용 | 작성자 |
|------|------|-----------|--------|
| v1.0 | 2025년 | 최초 작성 | PM |
| v1.1 | 2025년 | 키움증권 연동 구조 변경 — Windows Bridge Server 제거, 키움 REST API 직접 연동으로 전면 수정. 인프라에서 Windows EC2 제거 | PM |
| v1.2 | 2025년 | Backend API 및 Bot Engine 언어/프레임워크 변경 — Node.js(NestJS/TS) → Python(FastAPI). 디렉토리 구조, Exchange Adapter 인터페이스(TS→Python ABC), Bot Engine Worker(TS→Celery Task) 전면 재작성. shared 패키지 구조 추가 | PM |
| v1.3 | 2025년 | fastapi/full-stack-fastapi-template 기반으로 전환. Frontend: Next.js App Router → Vite+React+TanStack Router. Backend: 디렉토리 구조를 템플릿 기준으로 재정렬 (models.py, crud.py 방식 채택). shared/ 패키지 구조 제거, exchange_adapters를 backend/app 내부로 통합. 템플릿 제공 항목과 신규 추가 항목 명시 | PM |
| v1.4 | 2025년 | 인프라 전략 변경 — AWS 단일 구성 → On-premise 우선 + 클라우드 단계적 전환. Phase 1: 홈서버 + Docker Compose + Nginx + Certbot. Phase 2: AWS ECS/RDS/ElastiCache (사용자 증가 시). 네트워크 보안 다이어그램 Phase별 분리 기술 | PM |

---

*본 문서는 기술 설계 확정 후 업데이트됩니다.*
