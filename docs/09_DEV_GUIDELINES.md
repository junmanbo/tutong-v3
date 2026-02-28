# 개발 가이드라인 / 코딩 컨벤션 (Dev Guidelines)

**프로젝트명:** AutoTrade Platform  
**문서 버전:** v2.0  
**작성일:** 2025년  
**기반 템플릿:** fastapi/full-stack-fastapi-template

---

## 목차

1. [개발 환경 세팅](#1-개발-환경-세팅)
2. [프로젝트 구조 및 파일별 역할](#2-프로젝트-구조-및-파일별-역할)
3. [패키지 관리 (uv)](#3-패키지-관리-uv)
4. [Python 코딩 컨벤션](#4-python-코딩-컨벤션)
5. [SQLModel 작성 규칙](#5-sqlmodel-작성-규칙)
6. [FastAPI 라우터 작성 규칙](#6-fastapi-라우터-작성-규칙)
7. [Celery 봇 엔진 규칙](#7-celery-봇-엔진-규칙)
8. [금융 계산 규칙](#8-금융-계산-규칙)
9. [보안 규칙](#9-보안-규칙)
10. [오류 처리 규칙](#10-오류-처리-규칙)
11. [프론트엔드 규칙](#11-프론트엔드-규칙)
12. [Git 브랜치 전략](#12-git-브랜치-전략)
13. [테스트 작성 규칙](#13-테스트-작성-규칙)
14. [변경 이력](#14-변경-이력)

---

## 1. 개발 환경 세팅

### 1.1 최초 세팅

```bash
# 1. 템플릿 클론
git clone https://github.com/fastapi/full-stack-fastapi-template.git autotrade-platform
cd autotrade-platform

# 2. .env 설정
cp .env.example .env
# .env에서 아래 값 반드시 변경:
# SECRET_KEY, FIRST_SUPERUSER_PASSWORD, POSTGRES_PASSWORD

# 3. 전체 스택 실행 (DB + 백엔드 + 프론트엔드 + Traefik + MailCatcher)
docker compose watch
```

### 1.2 백엔드 로컬 개발 (Docker 없이)

```bash
cd backend
uv sync                          # 의존성 설치
fastapi dev app/main.py          # 개발 서버 실행 (자동 재시작)
uv run alembic upgrade head      # 마이그레이션 적용
```

### 1.3 Bot Engine 로컬 실행

```bash
cd bot_engine
uv sync
uv run celery -A celery_app worker --loglevel=info
```

### 1.4 pre-commit 설치

```bash
cd backend
uv run prek install -f
```

### 1.5 개발 URL

| 서비스 | URL |
|--------|-----|
| 프론트엔드 | http://localhost:5173 |
| 백엔드 API | http://localhost:8000 |
| Swagger UI | http://localhost:8000/docs |
| Adminer (DB GUI) | http://localhost:8080 |
| MailCatcher | http://localhost:1080 |
| Traefik UI | http://localhost:8090 |

---

## 2. 프로젝트 구조 및 파일별 역할

```
autotrade-platform/
├── backend/
│   ├── app/
│   │   ├── api/
│   │   │   ├── deps.py              # 의존성 주입 (SessionDep, CurrentUser)
│   │   │   └── routes/
│   │   │       ├── login.py         # [템플릿] 인증 API
│   │   │       ├── users.py         # [템플릿] 사용자 관리
│   │   │       ├── utils.py         # [템플릿] 헬스체크, 테스트 이메일
│   │   │       ├── items.py         # [템플릿 예제 → 삭제 예정]
│   │   │       ├── accounts.py      # [추가] 거래소 계좌 연동
│   │   │       ├── bots.py          # [추가] 봇 CRUD + 시작/중지
│   │   │       ├── subscriptions.py # [추가] 구독/결제
│   │   │       └── admin.py         # [추가] 관리자 기능
│   │   ├── core/
│   │   │   ├── config.py            # [템플릿+수정] 환경변수 설정
│   │   │   ├── security.py          # [템플릿] JWT, 비밀번호 해싱
│   │   │   └── db.py                # [템플릿] DB 엔진, 초기화
│   │   ├── models.py                # [템플릿+추가] 모든 SQLModel 모델
│   │   ├── crud.py                  # [템플릿+추가] DB CRUD 함수
│   │   ├── utils.py                 # [템플릿] 이메일 유틸
│   │   └── main.py                  # [템플릿+수정] FastAPI 앱 + 라우터 등록
│   ├── alembic/                     # DB 마이그레이션
│   └── pyproject.toml               # 의존성
│
├── bot_engine/                      # [추가] Celery 봇 엔진
│   ├── workers/
│   │   ├── spot_grid.py             # Spot Grid 봇 Worker
│   │   ├── snowball.py              # Position Snowball Worker
│   │   ├── rebalancing.py           # Rebalancing Worker
│   │   ├── spot_dca.py              # Spot DCA Worker
│   │   └── algo_orders.py           # Algo Orders Worker
│   ├── strategies/                  # 봇 전략 핵심 로직 (순수 함수)
│   ├── exchange_adapters/
│   │   ├── base.py                  # AbstractExchangeAdapter
│   │   ├── binance.py
│   │   ├── upbit.py
│   │   ├── kis.py
│   │   └── kiwoom.py
│   ├── utils/
│   │   ├── decimal_utils.py         # 금융 계산 유틸
│   │   └── crypto.py                # AES-256-GCM 암복호화
│   ├── celery_app.py                # Celery 앱 설정
│   ├── scheduler.py                 # APScheduler
│   └── pyproject.toml
│
├── frontend/
│   ├── src/
│   │   ├── client/                  # [자동생성 — 수정 금지]
│   │   ├── routes/_layout/
│   │   │   ├── index.tsx            # [수정] 대시보드
│   │   │   ├── bots.tsx             # [추가] 봇 목록
│   │   │   ├── accounts.tsx         # [추가] 거래소 계좌
│   │   │   ├── settings.tsx         # [템플릿] 사용자 설정
│   │   │   └── admin.tsx            # [수정] 관리자
│   │   └── components/
│   │       ├── Bots/                # [추가] 봇 컴포넌트
│   │       └── Charts/              # [추가] 차트 컴포넌트
│   └── package.json
│
├── compose.yml                      # [수정] Redis + bot_engine 추가
├── .env                             # [수정] 거래소/Celery 변수 추가
└── docs/
```

---

## 3. 패키지 관리 (uv)

템플릿이 uv를 기본으로 채택합니다. pip, poetry 사용 금지.

### 3.1 주요 명령어

```bash
# 의존성 설치
uv sync

# 패키지 추가
uv add httpx                      # 런타임 의존성
uv add --dev pytest               # 개발 의존성

# 패키지 제거
uv remove httpx

# 스크립트 실행
uv run pytest
uv run alembic upgrade head
uv run prek run --all-files       # 전체 파일 lint
```

### 3.2 backend/pyproject.toml — 추가 의존성

템플릿 기본 의존성 외에 이 프로젝트에서 추가합니다.

```toml
[project]
dependencies = [
    # 템플릿 기본 의존성은 유지 ...

    # 추가
    "celery[redis]>=5.3",
    "ccxt>=4.0",           # Binance·Upbit REST + WebSocket (watch_* 메서드 통합)
    "httpx>=0.27",         # KIS·키움증권 REST API (CCXT 미지원)
    "cryptography>=42.0",  # AES-256-GCM API Key 암호화
    "apscheduler>=3.10",   # DCA·Rebalancing 주기 실행
]
```

### 3.3 uv.lock 관리

`uv.lock`은 반드시 Git에 커밋합니다. `requirements.txt` 역할을 합니다.

---

## 4. Python 코딩 컨벤션

### 4.1 스타일 도구 (템플릿 그대로)

| 도구 | 역할 |
|------|------|
| **Ruff** | 린터 + 포매터 |
| **prek** | pre-commit 실행 (pre-commit 대체) |
| **mypy** | 정적 타입 검사 |

커밋 전 자동 실행됩니다 (`prek install -f` 후).

수동 실행:
```bash
cd backend
uv run prek run --all-files
```

### 4.2 네이밍 규칙

| 대상 | 규칙 | 예시 |
|------|------|------|
| 변수, 함수 | `snake_case` | `get_bot_by_id()` |
| 클래스 | `PascalCase` | `BinanceAdapter` |
| 상수 | `UPPER_SNAKE_CASE` | `MAX_GRID_COUNT = 200` |
| SQLModel 테이블 클래스 | `PascalCase` (단수) | `Bot`, `ExchangeAccount` |
| SQLModel Base/Public 클래스 | `{Entity}Base`, `{Entity}Public` | `BotBase`, `BotPublic` |
| 라우터 파일 | `snake_case.py` | `accounts.py` |

### 4.3 타입 힌트

모든 함수에 타입 힌트 필수 (mypy strict 기준):

```python
# ❌ 금지
def get_bot(bot_id):
    ...

# ✅ 올바른 방법
def get_bot(*, session: Session, bot_id: uuid.UUID) -> Bot | None:
    ...
```

---

## 5. SQLModel 작성 규칙

### 5.1 모델 정의 패턴

템플릿의 `models.py` 패턴을 그대로 따릅니다.

```python
# models.py에 추가하는 방식

# 1. Base — 공통 필드 (API 요청/응답 + DB 공용)
class BotBase(SQLModel):
    name: str = Field(max_length=100)
    bot_type: BotTypeEnum
    config: dict = Field(default={}, sa_column=Column(JSONB))

# 2. table=True — 실제 DB 테이블
class Bot(BotBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(
        foreign_key="user.id", nullable=False, ondelete="CASCADE"
    )
    status: BotStatusEnum = Field(default=BotStatusEnum.stopped)
    total_profit: Decimal = Field(default=Decimal("0"), max_digits=30, decimal_places=10)
    deleted_at: datetime | None = Field(default=None)
    created_at: datetime = Field(
        default_factory=get_datetime_utc,
        sa_type=DateTime(timezone=True),
    )
    # Relationships
    owner: "User" = Relationship(back_populates="bots")
    orders: list["BotOrder"] = Relationship(back_populates="bot")

# 3. Create — 생성 요청
class BotCreate(BotBase):
    exchange_account_id: uuid.UUID

# 4. Update — 수정 요청
class BotUpdate(SQLModel):
    name: str | None = Field(default=None, max_length=100)

# 5. Public — API 응답 (민감 필드 제외)
class BotPublic(BotBase):
    id: uuid.UUID
    status: BotStatusEnum
    total_profit: Decimal
    created_at: datetime

# 6. 목록 응답 (템플릿 패턴)
class BotsPublic(SQLModel):
    data: list[BotPublic]
    count: int
```

### 5.2 테이블명 규칙

SQLModel은 클래스명 소문자로 테이블명 자동 생성합니다.

| 클래스명 | 자동 생성 테이블명 |
|---------|-----------------|
| `Bot` | `bot` |
| `ExchangeAccount` | `exchangeaccount` |
| `BotOrder` | `botorder` |
| `UserSubscription` | `usersubscription` |

외래키 참조 시 이 테이블명을 사용합니다:

```python
user_id: uuid.UUID = Field(foreign_key="user.id")         # ✅
user_id: uuid.UUID = Field(foreign_key="users.id")        # ❌ 오류
```

### 5.3 JSONB 컬럼 사용

봇 config, 거래소 extra 정보 등은 JSONB로 저장합니다.

```python
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field

config: dict = Field(default={}, sa_column=Column(JSONB))
```

### 5.4 Soft Delete 조건

`users`, `bots`, `exchangeaccount` 테이블은 Soft Delete 사용.
조회 쿼리에 항상 `deleted_at.is_(None)` 조건 포함합니다.

```python
# ❌ 금지
statement = select(Bot).where(Bot.user_id == user_id)

# ✅ 올바른 방법
statement = select(Bot).where(
    Bot.user_id == user_id,
    Bot.deleted_at.is_(None)
)
```

### 5.5 Alembic 마이그레이션

모델 변경 후 반드시 마이그레이션 생성합니다.

```bash
cd backend

# 변경 사항 자동 감지 후 마이그레이션 파일 생성
uv run alembic revision --autogenerate -m "add_bot_tables"

# 생성된 파일 반드시 검토 후 적용
uv run alembic upgrade head

# 롤백
uv run alembic downgrade -1
```

**마이그레이션 파일 작성 규칙:**
- `--autogenerate` 결과물은 반드시 직접 검토 후 커밋
- 모든 마이그레이션은 `upgrade()` + `downgrade()` 쌍으로 작성
- 컬럼 삭제는 단계적으로: 코드에서 참조 제거 → 배포 → 삭제 마이그레이션

---

## 6. FastAPI 라우터 작성 규칙

### 6.1 라우터 파일 구조

템플릿 `routes/items.py`를 참고하여 동일한 패턴으로 작성합니다.

```python
# backend/app/api/routes/bots.py
import uuid
from typing import Any
from fastapi import APIRouter, HTTPException
from sqlmodel import select

from app import crud
from app.api.deps import CurrentUser, SessionDep
from app.models import (
    Bot, BotCreate, BotPublic, BotsPublic, BotUpdate, Message
)

router = APIRouter(prefix="/bots", tags=["bots"])


@router.get("/", response_model=BotsPublic)
def read_bots(
    session: SessionDep,
    current_user: CurrentUser,
    skip: int = 0,
    limit: int = 100,
) -> Any:
    """봇 목록 조회"""
    bots = crud.get_bots_by_user(
        session=session, user_id=current_user.id, skip=skip, limit=limit
    )
    return BotsPublic(data=bots, count=len(bots))


@router.post("/", response_model=BotPublic)
def create_bot(
    *,
    session: SessionDep,
    current_user: CurrentUser,
    bot_in: BotCreate,
) -> Any:
    """봇 생성"""
    # 플랜 한도 체크
    bot_count = crud.count_active_bots(session=session, user_id=current_user.id)
    plan_limit = crud.get_user_bot_limit(session=session, user_id=current_user.id)
    if plan_limit != -1 and bot_count >= plan_limit:
        raise HTTPException(status_code=409, detail="Bot limit exceeded for current plan")

    return crud.create_bot(session=session, bot_in=bot_in, owner_id=current_user.id)
```

### 6.2 라우터 등록

`backend/app/main.py`에 새 라우터를 등록합니다.

```python
# main.py
from app.api.routes import accounts, bots, subscriptions, admin

api_router.include_router(accounts.router)
api_router.include_router(bots.router)
api_router.include_router(subscriptions.router)
api_router.include_router(admin.router)
```

### 6.3 의존성 주입

템플릿이 제공하는 의존성을 그대로 사용합니다.

```python
from app.api.deps import (
    CurrentUser,          # 로그인된 현재 사용자
    SessionDep,           # DB 세션
    get_current_active_superuser,  # 관리자 전용 엔드포인트
)
```

### 6.4 HTTP 상태 코드

| 상황 | 코드 |
|------|------|
| 조회 성공 | `200` |
| 생성 성공 | `201` (response_model과 함께) |
| 인증 필요 | `401` |
| 권한 없음 | `403` |
| 리소스 없음 | `404` |
| 비즈니스 규칙 위반 | `409` |

---

## 7. Celery 봇 엔진 규칙

### 7.1 Celery 앱 설정

```python
# bot_engine/celery_app.py
from celery import Celery
import os

celery_app = Celery(
    "bot_engine",
    broker=os.environ["REDIS_URL"],
    backend=os.environ["REDIS_URL"],
    include=[
        "bot_engine.workers.spot_grid",
        "bot_engine.workers.snowball",
        "bot_engine.workers.rebalancing",
        "bot_engine.workers.spot_dca",
        "bot_engine.workers.algo_orders",
    ],
)

celery_app.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_acks_late=True,        # Worker 비정상 종료 시 재큐잉
    task_reject_on_worker_lost=True,
)
```

### 7.2 Worker Task 작성 규칙

```python
# bot_engine/workers/spot_grid.py
from celery import Task
from bot_engine.celery_app import celery_app
import logging

logger = logging.getLogger(__name__)


class BotTask(Task):
    """봇 Task 기반 클래스 — 공통 오류 처리"""
    abstract = True

    def on_failure(self, exc, task_id, args, kwargs, einfo):
        bot_id = kwargs.get("bot_id")
        logger.error(f"Bot task failed: bot_id={bot_id}, error={exc}")
        # DB 봇 상태를 'error'로 업데이트


@celery_app.task(
    bind=True,
    base=BotTask,
    name="bot_engine.workers.spot_grid.run",
    max_retries=0,          # 봇 Task 자동 재시도 금지 (수동 재시작)
    acks_late=True,
)
def run_spot_grid(self, *, bot_id: str) -> None:
    """Spot Grid 봇 실행"""
    import redis
    r = redis.from_url(os.environ["REDIS_URL"])

    while True:
        # 종료 신호 확인
        if r.get(f"bot:{bot_id}:stop"):
            r.delete(f"bot:{bot_id}:stop")
            logger.info(f"Bot {bot_id} stopped by signal")
            break

        # 봇 전략 실행 로직
        ...
```

**봇 Task 공통 규칙:**

| 규칙 | 이유 |
|------|------|
| `max_retries=0` | 봇 오류는 사용자 확인 후 수동 재시작 |
| `acks_late=True` | Worker 비정상 종료 시 재큐잉 보장 |
| 무한루프 + 종료 신호 | WebSocket 이벤트 지속 처리 |

### 7.3 봇 시작/중지 흐름

```python
# backend/app/api/routes/bots.py

@router.post("/{bot_id}/start")
def start_bot(bot_id: uuid.UUID, session: SessionDep, current_user: CurrentUser):
    bot = crud.get_bot(session=session, bot_id=bot_id, user_id=current_user.id)
    if not bot:
        raise HTTPException(status_code=404)
    if bot.status != BotStatusEnum.stopped:
        raise HTTPException(status_code=409, detail="Bot is not in stopped state")

    # Celery Task 시작
    from app.tasks import start_bot_task
    task = start_bot_task.delay(bot_id=str(bot_id))

    # DB 상태 업데이트
    bot.status = BotStatusEnum.pending
    bot.celery_task_id = task.id
    session.add(bot)
    session.commit()


@router.post("/{bot_id}/stop")
def stop_bot(bot_id: uuid.UUID, session: SessionDep, current_user: CurrentUser):
    bot = crud.get_bot(session=session, bot_id=bot_id, user_id=current_user.id)

    # Redis에 종료 신호 발행 → Worker가 다음 루프에서 감지
    import redis
    r = redis.from_url(settings.REDIS_URL)
    r.set(f"bot:{bot_id}:stop", "1", ex=300)
```

---

## 7-A. CCXT 사용 규칙 (Binance·Upbit 전용)

### 7-A.1 임포트 규칙

```python
# ✅ 항상 async_support 임포트 사용 (Celery Task 내 asyncio 사용)
import ccxt.async_support as ccxt

# ❌ 동기 ccxt 임포트 금지 (watch_* WebSocket 메서드 미지원)
import ccxt
```

### 7-A.2 거래소 인스턴스 생성 규칙

```python
# ✅ 올바른 생성 패턴
exchange = ccxt.binance({
    "apiKey": decrypt(enc_key, settings.ENCRYPTION_KEY),  # 복호화된 키 즉시 전달
    "secret": decrypt(enc_secret, settings.ENCRYPTION_KEY),
    "enableRateLimit": True,   # 필수 — 끄면 IP 차단 위험
    "options": {
        "defaultType": "spot",
        "adjustForTimeDifference": True,  # 서버 시간 자동 동기화 (Binance 필수)
    },
})

# ❌ 금지 — enableRateLimit 없이 생성
exchange = ccxt.binance({"apiKey": key, "secret": secret})
```

### 7-A.3 Decimal 변환 규칙

CCXT는 가격·수량을 Python `float`으로 반환합니다. 반드시 `str` 경유로 `Decimal` 변환해야 합니다.

```python
from decimal import Decimal

# ✅ 올바른 변환
price = Decimal(str(ticker["last"]))       # str 경유 필수
qty   = Decimal(str(order["amount"]))

# ❌ 부동소수점 오류 발생
price = Decimal(ticker["last"])            # float → Decimal 직접: 정밀도 손실
price = Decimal(float(ticker["last"]))     # 동일 문제

# ✅ None 방어 유틸리티 (CcxtExchangeAdapter._to_decimal 사용)
@staticmethod
def _to_decimal(value: float | str | None) -> Decimal:
    if value is None:
        return Decimal("0")
    return Decimal(str(value))
```

### 7-A.4 심볼 형식 규칙

```python
# ✅ 항상 CCXT 표준 형식 사용 (슬래시 구분)
await exchange.fetch_ticker("BTC/USDT")   # Binance
await exchange.fetch_ticker("BTC/KRW")   # Upbit

# ❌ 거래소 원본 형식 직접 사용 금지
await exchange.fetch_ticker("BTCUSDT")   # X — Binance 원본
await exchange.fetch_ticker("KRW-BTC")  # X — Upbit 원본

# DB 저장 심볼도 CCXT 표준 형식 기준
# bots.symbol 컬럼 예: "BTC/USDT", "BTC/KRW"
```

### 7-A.5 Celery Task 내 asyncio 사용 패턴

Celery Worker는 기본적으로 동기 실행 환경입니다. `ccxt.async_support`를 사용하려면 전용 이벤트 루프를 생성해야 합니다.

```python
# bot_engine/workers/base.py
import asyncio
from celery import Task

class AsyncBotTask(Task):
    """asyncio 코루틴을 Celery Task에서 안전하게 실행하는 베이스."""
    abstract = True

    def run_async(self, coro):
        """새 이벤트 루프를 생성해 코루틴 실행 후 루프 종료."""
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()


# bot_engine/workers/spot_grid.py
@celery_app.task(bind=True, base=AsyncBotTask, max_retries=0)
def run_spot_grid(self, *, bot_id: str) -> None:
    """Spot Grid 봇 실행 Task."""

    async def _run():
        exchange = ccxt.binance({
            "apiKey": decrypt(api_key_enc, settings.ENCRYPTION_KEY),
            "secret": decrypt(secret_enc, settings.ENCRYPTION_KEY),
            "enableRateLimit": True,
        })
        try:
            ticker = await exchange.fetch_ticker("BTC/USDT")
            price = Decimal(str(ticker["last"]))
            # ... 봇 로직 ...
        finally:
            await exchange.close()  # aiohttp 세션 반드시 정리

    self.run_async(_run())

# ❌ 금지 — Celery 스레드 내에는 이벤트 루프가 없음
asyncio.get_event_loop().run_until_complete(coro)
```

### 7-A.6 WebSocket 스트리밍 패턴

```python
# price_stream async generator — Celery Task 내부에서 호출
async def watch_price(exchange: ccxt.Exchange, symbol: str):
    """CCXT watch_ticker 기반 실시간 가격 스트림."""
    try:
        while True:
            # 종료 신호 확인 (Redis)
            if redis_client.get(f"bot:{bot_id}:stop"):
                break
            ticker = await exchange.watch_ticker(symbol)
            price = Decimal(str(ticker["last"]))
            # 봇 전략 로직 실행
            await process_tick(price)
    finally:
        await exchange.close()
```

### 7-A.7 예외 처리 규칙

```python
import ccxt

try:
    order = await exchange.create_order(...)
except ccxt.AuthenticationError:
    # API Key 만료 또는 잘못된 키 → 봇 중지 + 사용자 알림
    await stop_bot_with_error(bot_id, "AUTH_ERROR")
except ccxt.InsufficientFunds:
    # 잔고 부족 → 봇 중지
    await stop_bot_with_error(bot_id, "INSUFFICIENT_FUNDS")
except ccxt.InvalidOrder:
    # Lot size 위반, 최소 주문금액 미달 → 로그 후 다음 틱 대기
    logger.warning(f"Invalid order: {e}")
except ccxt.RateLimitExceeded:
    # enableRateLimit=True 임에도 burst 발생 시
    await asyncio.sleep(1)
except ccxt.NetworkError:
    # 네트워크 오류 → tenacity 재시도 처리
    raise
```

### 7-A.8 리소스 정리 규칙

```python
# ✅ 반드시 finally 블록에서 close() 호출
exchange = ccxt.binance({...})
try:
    result = await exchange.fetch_balance()
    return result
finally:
    await exchange.close()   # aiohttp ClientSession 정리 — 누락 시 리소스 누수

# ✅ 또는 async context manager 패턴 (Python 3.10+)
async with ccxt.binance({...}) as exchange:
    result = await exchange.fetch_balance()
```

---

> **가장 중요한 규칙입니다. 위반 시 실제 금전 손실이 발생합니다.**

### 8.1 Decimal 필수 사용

```python
from decimal import Decimal, ROUND_DOWN, ROUND_HALF_UP

# ❌ 절대 금지 — float 사용
price = 67230.5
total = price * 0.001   # 부동소수점 오류 발생

# ✅ 올바른 방법
price = Decimal("67230.5")
qty = Decimal("0.001")
total = price * qty     # 정확

# ❌ float에서 Decimal 직접 변환 금지
Decimal(0.001)          # 정밀도 손실 그대로 전파

# ✅ 반드시 문자열 경유
Decimal("0.001")
Decimal(str(float_value))   # float을 받아야 하는 경우
```

### 8.2 반올림 규칙

```python
# 매수 수량 — 항상 내림 (초과 주문 방지)
qty = (total_amount / price).quantize(Decimal("0.00000001"), rounding=ROUND_DOWN)

# 수익률 표시 — 반올림
pct = ((sell - buy) / buy * 100).quantize(Decimal("0.0001"), rounding=ROUND_HALF_UP)
```

### 8.3 거래소 Lot Size 준수

```python
# 거래소 심볼 정보에서 stepSize 조회 후 적용
def apply_lot_size(qty: Decimal, step_size: str) -> Decimal:
    step = Decimal(step_size)
    return (qty // step) * step   # 내림 처리
```

### 8.4 DB 컬럼 정밀도

```python
# SQLModel에서 금액 컬럼 정의
total_profit: Decimal = Field(
    default=Decimal("0"),
    max_digits=30,
    decimal_places=10
)
```

---

## 9. 보안 규칙

### 9.1 API Key 암복호화 — AES-256-GCM

```python
# bot_engine/utils/crypto.py
from cryptography.hazmat.primitives.ciphers.aead import AESGCM
import os, base64

def encrypt(plaintext: str, key: bytes) -> str:
    """AES-256-GCM 암호화. key는 정확히 32바이트."""
    aesgcm = AESGCM(key)
    nonce = os.urandom(12)
    ct = aesgcm.encrypt(nonce, plaintext.encode(), None)
    return base64.b64encode(nonce + ct).decode()

def decrypt(encrypted: str, key: bytes) -> str:
    data = base64.b64decode(encrypted)
    nonce, ct = data[:12], data[12:]
    return AESGCM(key).decrypt(nonce, ct, None).decode()
```

**원칙:**
- 저장 시: API 서버에서 암호화 후 DB 저장
- 복호화: Bot Engine에서만 수행 (API 응답에 절대 포함 금지)
- 암호화 키: 환경변수 `ENCRYPTION_KEY`에서만 로드

### 9.2 절대 금지

```python
# ❌ 로그에 민감 정보 출력
logger.info(f"api_key={api_key}")

# ❌ API 응답에 암호화된 값 포함
return {"api_key_enc": account.api_key_enc}

# ❌ 코드에 SECRET_KEY 하드코딩
SECRET_KEY = "my-secret-key"

# ❌ .env 파일 Git 커밋
# (.gitignore에 .env 반드시 포함)
```

### 9.3 입력 검증

SQLModel의 Field 검증을 활용합니다:

```python
class BotCreate(SQLModel):
    name: str = Field(min_length=1, max_length=100)
    grid_count: int = Field(ge=2, le=200)   # 2 ~ 200
    upper_price: Decimal = Field(gt=0)
```

---

## 10. 오류 처리 규칙

### 10.1 HTTPException 직접 사용 (템플릿 방식)

템플릿은 커스텀 예외 없이 `HTTPException`을 직접 사용합니다. 동일한 방식으로 작성합니다.

```python
from fastapi import HTTPException

# 리소스 없음
raise HTTPException(status_code=404, detail="Bot not found")

# 비즈니스 규칙 위반
raise HTTPException(status_code=409, detail="Bot limit exceeded")

# 권한 없음
raise HTTPException(status_code=403, detail="Not enough permissions")
```

### 10.2 거래소 API 오류 처리

```python
import asyncio
from tenacity import retry, stop_after_attempt, wait_exponential

@retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(min=1, max=10),
    reraise=True,
)
async def call_exchange_api(func, *args, **kwargs):
    try:
        return await func(*args, **kwargs)
    except RateLimitError:
        await asyncio.sleep(1)
        raise
    except AuthError:
        raise   # 인증 오류는 재시도 없이 즉시 실패
```

---

## 11. 프론트엔드 규칙

### 11.1 OpenAPI 클라이언트 자동 생성

백엔드 모델/라우터 변경 후 반드시 실행합니다.

```bash
bash scripts/generate-client.sh
```

`frontend/src/client/` 파일은 **직접 수정 금지** (다음 generate 시 덮어씌워짐).

### 11.2 API 호출 패턴

자동 생성된 클라이언트 사용:

```tsx
import { BotsService, type BotPublic } from "@/client"
import { useQuery, useMutation } from "@tanstack/react-query"

// 봇 목록 조회
const { data: bots } = useQuery({
    queryKey: ["bots"],
    queryFn: () => BotsService.readBots(),
})

// 봇 생성
const createBot = useMutation({
    mutationFn: (data: BotCreate) => BotsService.createBot({ requestBody: data }),
    onSuccess: () => queryClient.invalidateQueries({ queryKey: ["bots"] }),
})
```

### 11.3 라우터 추가 (TanStack Router)

```tsx
// frontend/src/routes/_layout/bots.tsx
import { createFileRoute } from "@tanstack/react-router"

export const Route = createFileRoute("/_layout/bots")({
    component: BotsPage,
})

function BotsPage() {
    return <div>봇 목록</div>
}
```

### 11.4 컴포넌트 작성

템플릿의 기존 컴포넌트 패턴을 최대한 재활용합니다.

- `DataTable` 컴포넌트: 봇 목록, 주문 내역 테이블에 활용
- `shadcn/ui` 컴포넌트: Dialog, Form, Button 등 기존 것 사용
- 새 컴포넌트: `components/Bots/`, `components/Charts/` 디렉토리에 추가

---

## 12. Git 브랜치 전략

**GitHub Flow** (1인 개발 기준):

```
main
  └── feat/bot-grid-engine
  └── feat/binance-adapter
  └── fix/order-decimal-calc
  └── chore/add-redis-to-compose
```

**브랜치 네이밍:**

| 접두사 | 용도 | 예시 |
|--------|------|------|
| `feat/` | 기능 개발 | `feat/spot-grid-bot` |
| `fix/` | 버그 수정 | `fix/upbit-balance-parse` |
| `refactor/` | 리팩토링 | `refactor/exchange-adapter` |
| `chore/` | 설정, 의존성 | `chore/add-recharts` |

**커밋 메시지 (Conventional Commits):**

```
feat: 거래소 계좌 연동 API 구현
fix: 바이낸스 잔고 Decimal 파싱 오류 수정
refactor: 거래소 어댑터 공통 재시도 로직 분리
chore: celery, httpx 의존성 추가
test: BinanceAdapter 주문 발행 단위 테스트 추가
```

**규칙:**
- `main` 브랜치 직접 커밋 금지
- 머지 전 `uv run bash scripts/test.sh` 통과 필수

---

## 13. 테스트 작성 규칙

### 13.1 테스트 구조

```
backend/tests/               # 템플릿 테스트 구조 유지
├── api/routes/
│   ├── test_login.py        # 템플릿
│   ├── test_users.py        # 템플릿
│   ├── test_bots.py         # 추가
│   └── test_accounts.py     # 추가
└── conftest.py              # 템플릿

bot_engine/tests/            # 추가
├── unit/
│   ├── test_decimal_utils.py
│   ├── test_strategies/
│   └── test_adapters/       # 파싱 로직 Mock 테스트
└── conftest.py
```

### 13.2 백엔드 테스트 실행

```bash
cd backend
uv run bash scripts/test.sh
```

### 13.3 단위 테스트 예시

```python
# bot_engine/tests/unit/test_decimal_utils.py
from decimal import Decimal
from bot_engine.utils.decimal_utils import apply_lot_size, calculate_pnl

def test_apply_lot_size_rounds_down():
    """수량 내림 처리 — 초과 주문 방지"""
    qty = Decimal("0.12345678")
    result = apply_lot_size(qty, step_size="0.0001")
    assert result == Decimal("0.1234")   # 내림, 올림 아님

def test_calculate_pnl():
    buy = Decimal("60000")
    sell = Decimal("63000")
    qty = Decimal("0.001")
    pnl, pct = calculate_pnl(buy, sell, qty)
    assert pnl == Decimal("3")
    assert pct == Decimal("5.0000")
```

### 13.4 커버리지 목표

| 레이어 | 목표 |
|--------|------|
| `bot_engine/utils/decimal_utils.py` | **100%** |
| `bot_engine/strategies/` | **90%+** |
| `bot_engine/exchange_adapters/` 파싱 로직 | **80%+** |
| `backend/app/api/routes/` | **70%+** |

---

## 14. 변경 이력

| 버전 | 날짜 | 변경 내용 |
|------|------|-----------|
| v1.0 | 2025년 | 최초 작성 (처음부터 개발 기준) |
| v2.0 | 2025년 | fastapi/full-stack-fastapi-template 기반으로 전면 재작성. SQLModel 패턴, 동기 세션, prek, uv, TanStack Router, OpenAPI 클라이언트 자동생성 등 템플릿 방식 반영 |
| v2.1 | 2025년 | 섹션 7-A 추가 — CCXT(`ccxt.async_support`) 사용 규칙. Binance·Upbit 어댑터 구현 가이드라인: 임포트 방식, 인스턴스 생성, Decimal 변환, 심볼 형식, Celery Task 내 asyncio 패턴, WebSocket 스트리밍, 예외 처리, 리소스 정리 |
