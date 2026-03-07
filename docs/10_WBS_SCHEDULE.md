# WBS / 개발 일정표 (Work Breakdown Structure)

**프로젝트명:** AutoTrade Platform
**문서 버전:** v1.0
**작성일:** 2025년
**작성자:** PM

---

## 전체 일정 개요

| 단계 | 기간 | 내용 |
|------|------|------|
| **Phase 0: 착수 및 설계** | 1~2주차 | 문서 완성, 개발 환경 구축, DB 설계 |
| **Phase 1-1: 기반 개발** | 3~6주차 | 인증, 계좌 연동, 기본 대시보드 |
| **Phase 1-2: 봇 엔진 개발** | 5~10주차 | 5가지 봇 전략 구현, 바이낸스 연동 |
| **Phase 1-3: 업비트 / KIS 연동** | 9~12주차 | 업비트, 한국투자증권 연동 |
| **Phase 1-4: 완성 및 QA** | 12~14주차 | 통합 테스트, 버그 수정, 배포 |
| **MVP 출시** | 14주차 | 베타 론칭 |

---

## 상세 WBS

### Phase 0: 착수 및 설계 (1~2주)

```
Week 1-2
├── [PM] 프로젝트 문서 완성
│   ├── 기획안 ✅
│   ├── 요구사항 명세서 ✅
│   ├── 시스템 아키텍처 설계서 ✅
│   ├── 기술 스택 정의서 ✅
│   ├── UI 설계서 ✅
│   ├── API 명세서 (작성 필요)
│   └── DB 설계서 (작성 필요)
│
├── [Dev] 개발 환경 구축
│   ├── GitHub 레포지토리 생성 ✅
│   ├── 템플릿 클론: git clone fastapi/full-stack-fastapi-template ✅
│   ├── .env 설정 + docker compose watch 실행 확인 ✅
│   ├── bot_engine/ 디렉토리 추가 (Celery Worker 초기 구조) ✅
│   └── CI/CD 파이프라인 기본 구성 (GitHub Actions)
│
└── [Design] Figma 와이어프레임 제작
    ├── 로그인/회원가입
    ├── 대시보드
    ├── 봇 생성 플로우 (5종)
    └── 봇 상세 페이지
```

### Phase 1-1: 기반 기능 개발 (3~6주)

```
Week 3-4: 백엔드 기반 (템플릿 확장)
├── [BE] 템플릿 제공 확인: 인증 API (로그인/회원가입/비밀번호 재설정) ✅
├── [BE] models.py — ExchangeAccount, Bot, BotOrder, BotLog 등 SQLModel 모델 추가 ✅
├── [BE] Alembic 마이그레이션 생성 및 적용 ✅
├── [BE] crud.py — Bot, ExchangeAccount CRUD 함수 추가 ✅
├── [BE] core/config.py — REDIS_URL, ENCRYPTION_KEY 등 설정 추가 ✅
└── [BE] compose.yml — Redis + bot_engine 서비스 추가 ✅

Week 4-5: 계좌 연동
├── [BE] API Key AES-256-GCM 암호화 유틸 구현 (bot_engine/utils/crypto.py) ✅
├── [BE] accounts.py — 거래소 계좌 연동 API (등록/조회/삭제) ✅
├── [BE] 바이낸스 Exchange Adapter 구현 (backend/app/exchange_adapters/) ✅
├── [BE] 업비트 Exchange Adapter 구현 ✅
├── [BE] 한국투자증권 Exchange Adapter 구현 ✅
└── [BE] 계좌 잔고 조회 API (엔드포인트 미구현 — Adapter 클래스만 존재)

Week 5-6: 프론트엔드 기반 (템플릿 확장)
├── [FE] 템플릿 제공 확인: 로그인/회원가입/설정 페이지 ✅
├── [FE] generate-client.sh 실행 → 새 API 타입/클라이언트 자동 생성 ✅
├── [FE] routes/_layout/accounts.tsx — 거래소 계좌 연동 페이지 ✅
├── [FE] routes/_layout/bots.tsx — 봇 목록 페이지 (기본) ✅
└── [FE] routes/_layout/index.tsx — 대시보드 홈 교체 (잔고 조회) ✅

── 추가 완료 (Phase 1-1 정리) ──
├── [BE] bots.py — 봇 CRUD API + 시작/중지 엔드포인트 ✅
├── [Test] backend API routes 테스트 (accounts, bots) ✅
├── [Test] backend CRUD 테스트 (accounts, bots) ✅
├── [Test] bot_engine 유틸리티 테스트 (decimal_utils, crypto) ✅
├── [FE] Items 예제 코드 전체 삭제 (routes, components, sidebar) ✅
└── [Dev] compose.yml bot_engine networks 선언 + bots.py import 정리 ✅
```

### Phase 1-2: 봇 엔진 개발 (5~10주)

```
Week 5-6: 봇 엔진 기반
├── [Bot] bot_engine/ 디렉토리 초기화 (pyproject.toml, celery_app.py) ✅
├── [Bot] Celery Worker 기본 구조 구현 (Broker: Redis) ✅
├── [Bot] AbstractExchangeAdapter 인터페이스 정의 ✅
├── [Bot] bot_engine/exchange_adapters/ — backend adapter re-export (path dep) ✅
├── [BE] bots.py — 봇 CRUD API + 시작/중지 엔드포인트 ✅
├── [BE] GET /accounts/{id}/balance — 잔고 조회 API 구현 ✅
└── [FE] generate-client.sh 실행 → 봇/잔고 관련 타입 자동 생성 ✅

Week 7-8: Spot Grid + DCA 봇
├── [Bot] Spot Grid 전략 로직 구현 ✅
│   ├── 그리드 레벨 계산 (Arithmetic / Geometric) ✅
│   ├── 체결 감지 (30초 폴링 + get_order) ✅
│   └── 체결 후 카운터 주문 배치 (on_buy_filled / on_sell_filled) ✅
├── [Bot] Spot DCA 전략 로직 구현 ✅
│   ├── 인터벌 기반 매수 타이밍 체크 ✅
│   └── 시장가/지정가 주문 발행 + Redis 상태 저장 ✅
├── [FE] 봇 생성 UI - Spot Grid/Spot DCA 폼 반영 (bots.tsx 단일 모달) ✅
└── [FE] 봇 생성 UI - 봇 타입별 입력 분기(5종 공통 확장) ✅

Week 8-9: Snowball + Rebalancing 봇
├── [Bot] Position Snowball 전략 로직 구현 ✅
│   ├── 가격 하락 조건 체크 (should_add_buy) ✅
│   └── 평균 매입가 기반 익절 청산 (should_take_profit) ✅
├── [Bot] Rebalancing Bot 전략 로직 구현 ✅
│   ├── 비중 계산 로직 (calc_weights) ✅
│   ├── 임계값 기반 트리거 (needs_rebalance) ✅
│   └── 매도 우선 리밸런싱 주문 발행 ✅
├── [FE] 봇 생성 UI - Position Snowball 폼 반영 ✅
└── [FE] 봇 생성 UI - Rebalancing 폼 반영 ✅

Week 9-10: Algo Orders + 공통 봇 기능
├── [Bot] Spot Algo Orders (TWAP) 로직 구현 ✅
│   ├── 슬라이스 수량 계산 (calc_slice_qty, calc_remaining_qty) ✅
│   └── 인터벌 계산 + 슬라이스 순차 실행 ✅
├── [Bot] 봇 손절/목표 수익 자동 종료 로직 ✅
├── [Bot] 봇 실행 로그 DB 저장 ✅
├── [Bot] strategies/ 테스트 코드 (커버리지 90%+) ✅ (현재 100%)
├── [FE] 봇 생성 UI - Algo Orders 폼 반영 ✅
├── [FE] 봇 목록 페이지 ✅
├── [FE] 봇 상세 / 운영 현황 페이지 ✅
├── [FE] 봇 생성 UI 5종 상세 라우트 분리 (/bots/new/*) ✅
├── [FE] 설정 페이지 라우트 분리 (/settings/profile, /settings/security, /settings/notifications) ✅
├── [FE] 구독/결제 라우트 분리 (/billing/plans, /billing/history) ✅
└── [FE] 대시보드 차트 실데이터 기반 연동 (accounts/balance, bots) ✅
```

### Phase 1-3: 추가 거래소 연동 + 알림 (9~12주)

```
Week 9-10: 업비트 연동
├── [Bot] 업비트 Exchange Adapter 구현 ✅
│   ├── REST API (주문, 잔고, 시세) ✅
│   └── WebSocket (실시간 가격)
└── [BE] 업비트 연동 테스트 ✅ (adapter 검증 테스트 추가)

Week 10-11: 한국투자증권 연동
├── [Bot] KIS OpenAPI Adapter 구현 ✅
│   ├── OAuth 2.0 토큰 발급 ✅
│   ├── 주식 주문 API 연동 ✅
│   └── 실시간 시세 WebSocket
└── [BE] KIS 연동 테스트 ✅ (adapter 검증 테스트 추가)

Week 11-12: 알림 + 대시보드 고도화
├── [BE] 이메일 알림 서비스 구현 (SES/SendGrid)
├── [BE] 알림 이벤트 트리거 로직
├── [FE] 알림 설정 페이지 ✅
├── [FE] 대시보드 차트 (수익 추이, 포트폴리오 비중) ✅
└── [FE] 구독 / 결제 페이지 (PG 연동 제외 UI 우선) ✅
```

### Phase 1-4: QA 및 배포 (12~14주)

```
Week 12-13: 통합 테스트 및 버그 수정
├── [QA] 회원가입 / 로그인 테스트
├── [QA] 계좌 연동 테스트 (4개 기관)
├── [QA] 5가지 봇 시나리오 테스트
├── [QA] 봇 중지/손절 동작 테스트
├── [QA] 보안 테스트 (API Key 암호화 검증)
├── [QA] 부하 테스트 (동시 봇 100개 이상)
└── [Dev] 발견된 버그 수정

Week 13-14: 배포 준비 및 론칭
├── [Dev] 홈서버 운영 환경 구성
│   ├── Ubuntu 서버 세팅 + Docker 설치
│   ├── compose.prod.yml 작성 (adminer·mailcatcher 제거, Nginx 추가)
│   ├── Nginx 리버스 프록시 설정
│   └── Certbot + Let's Encrypt SSL 적용
├── [Dev] DDNS 설정 (DuckDNS / Cloudflare) + 도메인 연결
├── [Dev] .env 운영 환경 변수 설정 (ENCRYPTION_KEY 등)
├── [Dev] GitHub Actions CI/CD — 서버 자동 배포 파이프라인 구성
├── [Dev] Prometheus + Grafana + Loki 모니터링 스택 구성
├── [Dev] Sentry 에러 트래킹 설정
├── [Dev] PostgreSQL 자동 백업 스크립트 (cron + pg_dump)
├── [PM] 서비스 약관 / 개인정보처리방침 작성
└── 🚀 베타 론칭
```

---

## 마일스톤 요약

```
Week  1-2  │ ✅ 설계 문서 완성 / 개발 환경 구축
Week  4    │ ✅ 회원 인증 / 계좌 연동 API 완성
Week  6    │ ✅ 기본 대시보드 + Exchange Adapter 완성 (백엔드 + 프론트 완료)
Week  8    │ ✅ Spot Grid + DCA 봇 동작 확인
Week 10    │ ✅ 전체 봇 5종 구현 완료
Week 12    │ 🔄 업비트 + KIS 연동/검증 대부분 완료, 알림 백엔드 구현 진행 중
Week 14    │ 🚀 MVP 베타 론칭
```

---

## 리소스 계획 (팀 구성 예시)

| 역할 | 인원 | 담당 |
|------|------|------|
| PM | 1명 | 문서, 일정 관리, 기획 |
| Frontend | 1~2명 | Vite + React (TanStack Router) 개발 — 템플릿 기반 |
| Backend | 1~2명 | FastAPI API 개발 (Python) — 템플릿 확장 |
| Bot Engine | 1명 | Celery Worker, 봇 전략 로직, 거래소 어댑터 (Python) |
| DevOps | 0.5명 | 인프라, CI/CD (겸직 가능) |
| Design | 0.5명 | Figma 디자인 (겸직 가능) |

> ⚡ 소규모 팀(2~3명)의 경우 Backend + Bot Engine을 한 명이 담당하고, Frontend + DevOps를 한 명이 담당하는 구조로 진행 가능합니다.

---

## 변경 이력

| 버전 | 날짜 | 변경 내용 | 작성자 |
|------|------|-----------|--------|
| v1.0 | 2025년 | 최초 작성 | PM |
| v1.1 | 2025년 | Backend/Bot Engine 기술 스택 변경 반영 — NestJS→FastAPI, BullMQ→Celery, Prisma→SQLAlchemy+Alembic, node-cron→APScheduler | PM |
| v1.2 | 2025년 | fastapi/full-stack-fastapi-template 기반 전환 — Phase 0 개발환경 구축: 템플릿 클론으로 변경. Phase 1-1 백엔드: 인증 API 구현 제거 (템플릿 제공), models.py/crud.py 확장으로 변경. Phase 1-1 프론트: Next.js 초기화 제거 (템플릿 제공), generate-client.sh + 추가 라우트 작성으로 변경. 리소스 계획: Next.js → Vite+React | PM |
| v1.3 | 2025년 | 인프라 전략 변경 — Phase 1-4 배포 태스크를 On-premise(홈서버) 기반으로 재작성. AWS Terraform 구성 → Docker Compose 운영 환경 + Nginx + Certbot + Prometheus/Grafana/Loki + GitHub Actions 자동 배포로 교체 | PM |
| v1.4 | 2026-03-04 | 진행 상황 반영 — Phase 0·1-1 백엔드 완료 표시, Phase 1-2 봇 엔진 기반 완료 표시, 테스트·정리 작업 추가 기록 | Dev |
| v1.5 | 2026-03-05 | Phase 1-1 프론트엔드 완료 표시 — accounts.tsx, bots.tsx, index.tsx 구현 완료 | Dev |
| v1.6 | 2026-03-05 | Phase 1-2 봇 전략 완료 — 5가지 strategies/ 순수 함수 + workers/ 실제 구현, GET /accounts/{id}/balance 추가 | Dev |
| v1.7 | 2026-03-05 | Phase 1-2 진행 반영 — bot_engine/strategies 테스트 보강(커버리지 100%), 봇 생성 UI 5종 입력 분기, 봇 상세/운영 현황 페이지 추가 | Dev |
| v1.8 | 2026-03-05 | E2E 테스트 정리 — 템플릿 잔재 items.spec.ts 삭제, 로그인/설정/리셋 테스트를 현재 UI 기준으로 정합화, Playwright 전체 51 pass / 2 skip 확인 | Dev |
| v1.9 | 2026-03-07 | 진행 현황 반영 — 봇 손절/목표수익 자동 종료 로직 완료, Upbit/KIS adapter 검증 테스트 추가, 봇 생성 UI 5종 상세 라우트 분리, 설정/구독 경로 분리, 대시보드 실데이터 시각화 반영 | Dev |
| v2.0 | 2026-03-07 | 운영 변경 반영 — GitHub Actions 워크플로우 비활성화(.github/workflows.disabled로 이동), 배포/CI는 수동 운영 기준으로 임시 전환 | Dev |
| v2.1 | 2026-03-07 | 봇 실행 로그 후속 완성 — BotLog 테이블/CRUD/API 추가, worker 주문/체결 이벤트 로그 저장, 봇 상세 로그 타임라인 실데이터 연동 | Dev |

---

*실제 일정은 팀 규모 및 상황에 따라 조정됩니다.*
