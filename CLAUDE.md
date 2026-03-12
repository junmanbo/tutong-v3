# AutoTrade Platform — Claude Code 가이드

국내 증권사(한국투자증권, 키움증권) + 글로벌 거래소(바이낸스, 업비트)를 하나의 플랫폼에서
통합 운영하는 **자동 매매 플랫폼**입니다.

> **개발 방식:** `fastapi/full-stack-fastapi-template` 기반으로 봇 엔진과 거래소 연동 기능을 추가합니다.
> 템플릿이 제공하는 코드는 최대한 그대로 사용하고, 이 프로젝트 고유 기능만 추가합니다.

---

## 참조 문서

| 문서 | 용도 |
|------|------|
| `docs/03_SYSTEM_ARCHITECTURE.md` | 전체 구조, 디렉토리 레이아웃, 데이터 흐름 |
| `docs/07_DATABASE_DESIGN.md` | 테이블 상세 정의, ERD, 인덱스 전략 |
| `docs/08_EXTERNAL_API_INTEGRATION.md` | 거래소별 인증/엔드포인트/WebSocket/Rate Limit |
| `docs/09_DEV_GUIDELINES.md` | 코딩 컨벤션, 실행 명령어, 테스트 규칙 |
| `docs/02_REQUIREMENTS.md` | 기능 요구사항 전체 목록 |

---

## 기술 스택

### 템플릿 기본 제공 (변경 금지)

| 레이어 | 기술 |
|--------|------|
| **Backend ORM** | SQLModel (SQLAlchemy + Pydantic 통합) |
| **인증** | PyJWT + pwdlib (argon2 + bcrypt) |
| **DB 드라이버** | psycopg 3 (동기) |
| **마이그레이션** | Alembic |
| **패키지 관리** | uv |
| **린트/포매터** | Ruff + mypy + prek |
| **Frontend** | Vite + React + TypeScript + Tailwind CSS |
| **Frontend 라우팅** | TanStack Router (파일 기반) |
| **Frontend 서버 상태** | TanStack Query |
| **Frontend UI** | shadcn/ui |
| **Frontend 린트** | Biome |
| **E2E 테스트** | Playwright |
| **인프라 (Phase 1)** | Docker Compose + Nginx + Certbot + Prometheus/Grafana/Loki (홈서버) |
| **인프라 (Phase 2)** | AWS ECS + RDS + ElastiCache + CloudFront (클라우드 전환 시) |

### 이 프로젝트에서 추가

| 레이어 | 기술 |
|--------|------|
| **봇 엔진** | Celery 5+ (Worker), APScheduler |
| **메시지 브로커** | Redis |
| **거래소 API (암호화폐)** | ccxt (`ccxt.async_support`) — Binance·Upbit REST + WebSocket |
| **WebSocket** | ccxt 내장 (`watch_*` 메서드) |
| **암호화** | cryptography (AES-256-GCM, API Key 암호화) |
| **차트** | Recharts, TradingView Lightweight Charts |

---

## 프로젝트 디렉토리 구조

```
autotrade-platform/
│
├── backend/                         # [템플릿] FastAPI 백엔드
│   ├── app/
│   │   ├── api/
│   │   │   ├── deps.py              # [템플릿] SessionDep, CurrentUser
│   │   │   └── routes/
│   │   │       ├── login.py         # [템플릿] 인증 API
│   │   │       ├── users.py         # [템플릿] 사용자 관리
│   │   │       ├── utils.py         # [템플릿] 헬스체크
│   │   │       ├── items.py         # [템플릿 예제 → 개발 초기 삭제]
│   │   │       ├── accounts.py      # [추가] 거래소 계좌 연동
│   │   │       ├── bots.py          # [추가] 봇 CRUD + 시작/중지
│   │   │       ├── subscriptions.py # [추가] 구독/결제
│   │   │       └── admin.py         # [추가] 관리자
│   │   ├── core/
│   │   │   ├── config.py            # [템플릿+수정] 환경변수
│   │   │   ├── security.py          # [템플릿] JWT, 비밀번호 해싱
│   │   │   └── db.py                # [템플릿] DB 엔진
│   │   ├── models.py                # [템플릿+추가] 모든 SQLModel 정의
│   │   ├── crud.py                  # [템플릿+추가] DB CRUD 함수
│   │   ├── exchange_adapters/       # [추가] 거래소 어댑터
│   │   │   ├── base.py              #   AbstractExchangeAdapter
│   │   │   ├── binance.py
│   │   │   ├── upbit.py
│   │   │   ├── kis.py
│   │   │   └── kiwoom.py
│   │   ├── utils.py                 # [템플릿] 이메일 유틸
│   │   └── main.py                  # [템플릿+수정] 앱 진입점
│   ├── alembic/                     # [템플릿] DB 마이그레이션
│   ├── tests/                       # [템플릿+추가] pytest 테스트
│   ├── pyproject.toml               # [템플릿+수정] 의존성
│   └── Dockerfile                   # [템플릿]
│
├── bot_engine/                      # [추가] Celery 봇 엔진
│   ├── workers/
│   │   ├── spot_grid.py             # Spot Grid 봇 Task
│   │   ├── snowball.py              # Position Snowball Task
│   │   ├── rebalancing.py           # Rebalancing Task
│   │   ├── spot_dca.py              # Spot DCA Task
│   │   └── algo_orders.py           # Algo Orders Task
│   ├── strategies/                  # 봇 전략 핵심 로직 (순수 함수)
│   ├── exchange_adapters/           # backend의 어댑터를 공유하거나 복사
│   ├── utils/
│   │   ├── decimal_utils.py         # 금융 계산 유틸
│   │   └── crypto.py                # AES-256-GCM 암복호화
│   ├── celery_app.py
│   ├── scheduler.py
│   └── pyproject.toml
│
├── frontend/                        # [템플릿] Vite + React SPA
│   └── src/
│       ├── client/                  # [자동생성 — 절대 수동 편집 금지]
│       ├── routes/_layout/
│       │   ├── index.tsx            # [수정] 대시보드
│       │   ├── settings.tsx         # [템플릿]
│       │   ├── admin.tsx            # [수정]
│       │   ├── bots.tsx             # [추가]
│       │   └── accounts.tsx         # [추가]
│       └── components/
│           ├── ui/                  # [템플릿] shadcn/ui
│           ├── Bots/                # [추가]
│           └── Charts/              # [추가]
│
├── compose.yml                      # [템플릿+수정] Redis, bot_engine 추가
├── compose.override.yml             # [템플릿] 로컬 개발용
├── .env                             # [수정] 거래소/Celery 변수 추가
├── scripts/
│   └── generate-client.sh          # [템플릿] OpenAPI → TS 클라이언트 자동생성
└── docs/                            # 설계 문서
```

---

## 핵심 규칙

### 1. 템플릿 코드 수정 최소화

템플릿이 제공하는 파일은 **필요한 경우에만 최소한으로 수정**합니다.
특히 `core/security.py`, `core/db.py`, `api/deps.py`는 건드리지 않는 것을 원칙으로 합니다.
새 기능은 새 파일(`routes/bots.py` 등)을 추가해서 구현합니다.

### 2. SQLModel 패턴 — 템플릿 방식 준수

```python
# ✅ 템플릿과 동일한 SQLModel 패턴
class BotBase(SQLModel):                    # 공통 필드 (API 공유)
    name: str = Field(max_length=100)
    bot_type: BotTypeEnum

class Bot(BotBase, table=True):             # DB 테이블
    id: uuid.UUID = Field(default_factory=uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="user.id", ondelete="CASCADE")
    config: dict = Field(default={}, sa_column=Column(JSONB))
    deleted_at: datetime | None = Field(default=None, sa_type=DateTime(timezone=True))
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(UTC),
        sa_type=DateTime(timezone=True),
    )

class BotCreate(BotBase):                   # POST 요청 스키마
    exchange_account_id: uuid.UUID

class BotPublic(BotBase):                   # GET 응답 스키마
    id: uuid.UUID
    status: BotStatusEnum

# ❌ 금지 — SQLAlchemy 단독 사용 (async 포함)
from sqlalchemy.ext.asyncio import AsyncSession
```

### 3. CRUD 패턴 — crud.py에 함수로 작성

```python
# ✅ 템플릿 방식 — crud.py에 함수로 추가
def get_bot(*, session: Session, bot_id: uuid.UUID) -> Bot | None:
    return session.get(Bot, bot_id)

def create_bot(*, session: Session, bot_in: BotCreate, owner_id: uuid.UUID) -> Bot:
    bot = Bot.model_validate(bot_in, update={"user_id": owner_id, "status": "stopped"})
    session.add(bot)
    session.commit()
    session.refresh(bot)
    return bot

# ❌ 금지 — 별도 service 클래스, async 쿼리
class BotService:
    async def create(self, db: AsyncSession, ...): ...
```

### 4. 라우터 패턴 — 템플릿 방식 준수

```python
# ✅ 템플릿 방식 — 동기 함수, 직접 HTTPException
from app.api.deps import CurrentUser, SessionDep

router = APIRouter(prefix="/bots", tags=["bots"])

@router.get("/", response_model=BotsPublic)
def read_bots(session: SessionDep, current_user: CurrentUser) -> Any:
    bots = crud.get_bots_by_user(session=session, user_id=current_user.id)
    return BotsPublic(data=bots, count=len(bots))

@router.post("/", response_model=BotPublic, status_code=201)
def create_bot(*, session: SessionDep, current_user: CurrentUser, bot_in: BotCreate) -> Any:
    return crud.create_bot(session=session, bot_in=bot_in, owner_id=current_user.id)

# ❌ 금지 — async def, 커스텀 예외 클래스
async def create_bot(...): ...
raise NotFoundError(...)   # HTTPException을 직접 사용할 것
```

### 5. Soft Delete

```python
# ✅ deleted_at 패턴 (users, bots, exchange_accounts)
bot.deleted_at = datetime.now(UTC)
session.commit()

# 조회 시 항상 포함
statement = select(Bot).where(Bot.user_id == user_id, Bot.deleted_at.is_(None))
```

### 6. 금액/가격/수량 — Decimal 필수

```python
from decimal import Decimal, ROUND_DOWN

# ❌ 절대 금지
price = 67230.5
qty = 0.001
Decimal(0.001)      # float → Decimal 직접 변환 금지

# ✅ 올바른 방법
price = Decimal("67230.5")
qty = Decimal("0.001")
qty_rounded = (total / price).quantize(Decimal("0.00000001"), rounding=ROUND_DOWN)
```

DB 금액 컬럼: `NUMERIC(30, 10)` 타입 사용.

### 7. API Key 암복호화 — AES-256-GCM

```python
from bot_engine.utils.crypto import encrypt, decrypt

# 저장 시 (백엔드 API)
api_key_enc = encrypt(plain_api_key, settings.ENCRYPTION_KEY)

# 사용 시 (Bot Engine만)
plain_api_key = decrypt(account.api_key_enc, settings.ENCRYPTION_KEY)
```

암호화 키는 환경변수에서만 로드. 로그/응답에 평문 또는 암호화값 절대 노출 금지.

### 8. 프론트엔드 — 자동생성 클라이언트 사용

```typescript
// ✅ 자동생성 클라이언트 사용 (backend API 스키마와 타입 동기화)
import { BotsService } from "@/client"

const { data: bots } = useQuery({
  queryKey: ["bots"],
  queryFn: () => BotsService.readBots(),
})

// ❌ 금지 — 직접 fetch/axios 호출
fetch("/api/v1/bots")
```

백엔드 API 변경 후 반드시 실행:
```bash
bash scripts/generate-client.sh
```

---

## 개발 환경 실행 명령어

```bash
# 전체 서비스 실행 (Docker — 권장)
docker compose watch

# 백엔드 로컬 실행 (DB는 Docker 사용)
cd backend && uv run fastapi dev app/main.py

# DB 마이그레이션 적용
cd backend && uv run alembic upgrade head

# 마이그레이션 파일 생성
cd backend && uv run alembic revision --autogenerate -m "add_bots"

# 테스트
cd backend && uv run pytest

# 린트 + 타입체크
cd backend && uv run prek run --all-files

# OpenAPI 클라이언트 자동생성 (백엔드 API 변경 후)
bash scripts/generate-client.sh

# 봇 엔진 워커 실행
cd bot_engine && uv run celery -A celery_app worker --loglevel=info
```

---

## 봇 타입 및 전략

| 봇 타입 | `bot_type` 값 | 전략 |
|---------|--------------|------|
| Spot Grid | `spot_grid` | 상하한 범위 그리드 반복 매매 |
| Position Snowball | `snowball` | 가격 하락 시 분할 매수 |
| Rebalancing | `rebalancing` | 다자산 목표 비중 유지 |
| Spot DCA | `spot_dca` | 정기 정액 자동 매수 |
| Spot Algo Orders | `algo_orders` | TWAP 대량 주문 분할 실행 |

**봇 상태:** `stopped` → `pending` → `running` → `completed` / `error`

**봇 중지 신호:** `redis.set(f"bot:{bot_id}:stop", "1")` → Worker가 다음 루프에서 감지 후 종료

---

## 거래소 어댑터

상세 내용 → `docs/08_EXTERNAL_API_INTEGRATION.md`

| 거래소 | 구현 방식 | 라이브러리 |
|--------|-----------|-----------|
| Binance | CCXT | `ccxt.async_support.binance` |
| Upbit | CCXT | `ccxt.async_support.upbit` |
| 한국투자증권 | 직접 구현 | `httpx` |
| 키움증권 | 직접 구현 | `httpx` |

### CCXT 핵심 규칙

```python
import ccxt.async_support as ccxt

# ✅ 생성 시 enableRateLimit 반드시 활성화
exchange = ccxt.binance({
    "apiKey": api_key,
    "secret": secret,
    "enableRateLimit": True,   # Rate Limit 자동 처리 — 필수
    "options": {"defaultType": "spot"},
})

# ✅ 심볼은 항상 CCXT 표준 형식 사용
ticker = await exchange.fetch_ticker("BTC/USDT")   # O
ticker = await exchange.fetch_ticker("BTCUSDT")    # X — 직접 거래소 형식 사용 금지

# ✅ CCXT float 반환값 → Decimal 변환 (str 경유 필수)
price = Decimal(str(ticker["last"]))   # O
price = Decimal(ticker["last"])        # X — float → Decimal 직접 변환 정밀도 오류

# ✅ 사용 완료 후 반드시 close() 호출 (aiohttp 세션 정리)
try:
    result = await exchange.fetch_balance()
finally:
    await exchange.close()
```

### Celery Task에서 CCXT 사용 패턴

Celery는 동기 환경이므로 `asyncio.new_event_loop()`를 통해 실행합니다.

```python
# ✅ 올바른 방법 — 전용 이벤트 루프 사용
class AsyncTask(Task):
    def run_async(self, coro):
        loop = asyncio.new_event_loop()
        try:
            return loop.run_until_complete(coro)
        finally:
            loop.close()

# ❌ 금지 — asyncio.get_event_loop() 사용 (Celery 스레드 내 이벤트 루프 없음)
asyncio.get_event_loop().run_until_complete(coro)
```

---

## 구독 플랜 제한

| 플랜 | 최대 봇 수 | 월 요금 |
|------|-----------|---------|
| Free | 1 | 무료 |
| Basic | 5 | ₩9,900 |
| Pro | 무제한 | ₩29,900 |

봇 생성 시 `crud.py`에서 플랜 한도 체크 필수.

---

## 보안 절대 금지 사항

```python
# ❌ 로그에 API Key, Secret 출력
logger.info(f"key={api_key}")

# ❌ API 응답에 암호화값 포함
return {"api_key_enc": account.api_key_enc}

# ❌ float 금액 계산
total = 67230.5 * 0.001

# ❌ SQL 문자열 포맷팅
session.exec(f"SELECT * FROM bot WHERE id = '{bot_id}'")

# ❌ .env 파일 Git 커밋
```

---

## Git 커밋 메시지

```
feat: Spot Grid 봇 전략 로직 구현
fix: 바이낸스 잔고 조회 Decimal 파싱 오류 수정
refactor: 거래소 어댑터 공통 재시도 로직 분리
chore: celery[redis] 의존성 추가
test: BinanceAdapter 단위 테스트 추가
```

브랜치: `feat/`, `fix/`, `refactor/`, `chore/`, `docs/` 접두사 사용.
`main` 브랜치 직접 커밋 금지.

---

## 현재 개발 단계

### 완료
- [x] 전체 설계 문서 완성
- [x] 기술 스택 확정 (템플릿 기반)
- [x] Phase 1-1: 기반 기능 개발 (백엔드 + 봇 엔진 기반 + 프론트엔드)
- [x] Phase 1-2: 봇 엔진 기반 구조 (Celery Worker, Exchange Adapter 구조)
- [x] Phase 1-2 계속: 봇 전략 로직 구현 + 잔고 조회 API
- [x] Phase 1-2 마무리(1차): 전략 테스트 보강 + 봇 생성 5종 폼 + 봇 상세/운영 현황 페이지
- [x] 프론트 E2E 테스트 정리: 템플릿 잔재(items) 제거, 현재 UI 기준 Playwright 정합화
- [x] Phase 1-3: 알림/Admin/Subscription API 완성 + Worker 버그 수정 + Bot.config 추가
- [x] UI 정합 1차(화면정의서 기준): 인증 경로(`/auth/*`), 회원가입 필수 동의, 상단 헤더 bell/profile
- [x] 계좌 등록 UX 개선: 저장 전 연결 테스트 API + 프론트 강제 플로우 반영
- [x] 봇 상세 최근 주문 개선: 로그 카드 → 실제 체결 매매내역 테이블 전환

### Phase 1-1 완료 세부 내역
1. ✅ 템플릿 클론 및 환경 설정
2. ✅ 템플릿 예제 코드 정리 (Items 백엔드/프론트 전체 삭제)
3. ✅ 봇/계좌 모델 추가 + Alembic 마이그레이션
4. ✅ 거래소 계좌 API 구현 (accounts.py + Exchange Adapters)
5. ✅ 봇 API 구현 (bots.py + start/stop Celery/Redis 연동)
6. ✅ 프론트엔드 타입 동기화 (generate-client.sh)
7. ✅ 프론트엔드 페이지 구현 (accounts.tsx, bots.tsx, index.tsx)
8. ✅ 테스트 코드 작성 (backend API/CRUD + bot_engine utils)

### Phase 1-2 완료 세부 내역
1. ✅ bot_engine/strategies/ — 5가지 봇 전략 순수 함수 구현
   - spot_dca.py: should_buy, calc_order_qty, is_completed
   - spot_grid.py: build_grid, on_buy_filled, on_sell_filled
   - snowball.py: should_add_buy, should_take_profit, calc_avg_price
   - rebalancing.py: calc_weights, needs_rebalance, calc_rebalance_orders
   - algo_orders.py: calc_slice_qty, calc_interval, calc_remaining_qty
2. ✅ bot_engine/workers/ — 5가지 Worker 실제 구현 (TODO → 동작 코드)
   - Redis 상태 저장 (재시작 복원), 1분 단위 stop 신호 확인
3. ✅ 계좌 잔고 조회 API: GET /accounts/{id}/balance
4. ✅ app.core.crypto에 decrypt() 추가 (backend 내부 사용)
5. ✅ 봇 실행 로그 API + Worker 주문/체결 이벤트 로그 저장
6. ✅ 알림 시스템 (Notification 모델, 이벤트 트리거, 알림 설정 API)

### Phase 1-3 완료 세부 내역
1. ✅ Bot.config JSONB 필드 + Alembic 마이그레이션 (b4c5d6e7f8a9)
2. ✅ Worker 버그 수정: `ticker.price`, `order.exchange_order_id`, `OrderRequest.qty`
3. ✅ bot_engine DB 엔진 싱글턴 (_get_db_session 모듈-레벨 캐싱)
4. ✅ 계좌 등록 시 API Key 유효성 검증 (validate_credentials 호출)
5. ✅ 알림 목록/읽음 처리 API: GET /notifications/, POST /notifications/{id}/read, POST /notifications/read-all
6. ✅ Admin 라우터: GET /admin/users, PATCH /admin/users/{id}/deactivate|activate, GET /admin/bots
7. ✅ Subscription 라우터: GET /subscriptions/plans, GET /subscriptions/me, DELETE /subscriptions/me/cancel
8. ✅ 봇 생성 5종 폼에서 config 파라미터 API 전달
9. ✅ TypeScript 클라이언트 재생성 (Admin/Notifications/Subscriptions 서비스 포함)

### 지금 해야 할 작업 (Phase 1-4)
1. UI 설계서 대비 미반영 화면/상태(탭/필터/버튼 동작) 잔여 항목 정리
2. 봇/계좌 통합 E2E 시나리오 보강 (실행→주문→체결→상세 반영)
3. KIS `order_update_stream`, Kiwoom `price_stream/order_update_stream` 실시간 연동
4. 운영 환경 점검 (compose.prod.yml, Nginx, SSL, Prometheus/Grafana)

---

## 테스트 커버리지 목표

| 레이어 | 목표 |
|--------|------|
| `bot_engine/utils/decimal_utils.py` | **100%** |
| `bot_engine/strategies/` | **90%+** |
| `backend/app/exchange_adapters/` 파싱 로직 | **80%+** |
| `backend/app/api/routes/` | **70%+** |
