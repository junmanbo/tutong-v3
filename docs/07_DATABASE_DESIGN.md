# 데이터베이스 설계서 (Database Design)

**프로젝트명:** AutoTrade Platform  
**문서 버전:** v1.0  
**작성일:** 2025년  
**작성자:** PM / Tech Lead  
**DBMS:** PostgreSQL 16+

---

## 목차

1. [설계 원칙 및 주요 결정사항](#1-설계-원칙-및-주요-결정사항)
2. [ERD 다이어그램 (텍스트)](#2-erd-다이어그램-텍스트)
3. [테이블 목록 및 역할](#3-테이블-목록-및-역할)
4. [테이블 상세 정의](#4-테이블-상세-정의)
5. [인덱스 전략](#5-인덱스-전략)
6. [파티셔닝 전략](#6-파티셔닝-전략)
7. [Enum 타입 정의](#7-enum-타입-정의)
8. [공통 컬럼 규칙](#8-공통-컬럼-규칙)
9. [SQLAlchemy 모델 매핑 가이드](#9-sqlalchemy-모델-매핑-가이드)
10. [변경 이력](#10-변경-이력)

---

## 1. 설계 원칙 및 주요 결정사항

### 1.1 핵심 원칙

| 원칙 | 내용 |
|------|------|
| **UUID PK** | 모든 테이블 PK는 `UUID` 사용. 보안상 순차 ID 노출 방지, 분산 환경 확장성 확보 |
| **Soft Delete** | 사용자·봇·계좌 등 핵심 데이터는 `deleted_at` 컬럼으로 소프트 삭제. 감사 추적 및 데이터 복구 대비 |
| **Decimal 정밀도** | 금융 수치(가격, 수량, 금액)는 모두 `NUMERIC(36, 18)` 사용. Python `decimal.Decimal`과 정확히 매핑 |
| **타임존** | 모든 `TIMESTAMPTZ` 컬럼은 UTC 기준으로 저장. 표시는 애플리케이션 레이어에서 KST 변환 |
| **API Key 암호화** | `exchange_accounts.api_key_enc`, `api_secret_enc`는 AES-256-GCM으로 암호화된 값 저장. 복호화 키는 AWS Secrets Manager 관리 |

### 1.2 봇 설정값 저장 방식 결정

봇 타입마다 파라미터 구조가 상이하므로, **공통 컬럼 + 타입별 별도 설정 테이블** 방식을 채택합니다.

```
bots (공통 정보)
  ├── bot_config_grid        (Spot Grid 전용 설정)
  ├── bot_config_snowball    (Position Snowball 전용 설정)
  ├── bot_config_rebalancing (Rebalancing 전용 설정)
  │     └── bot_config_rebal_assets (리밸런싱 자산 목록)
  ├── bot_config_dca         (Spot DCA 전용 설정)
  └── bot_config_algo        (Algo Orders 전용 설정)
```

**채택 이유:**
- JSON 단일 컬럼 방식 대비 컬럼 레벨 제약(NOT NULL, CHECK)으로 데이터 무결성 보장
- 단일 타입 테이블 분리 방식 대비 테이블 수를 합리적으로 유지하면서 타입 안전성 확보
- SQLAlchemy에서 `relationship()` + `uselist=False`로 깔끔하게 매핑 가능

### 1.3 수익 이력 저장 방식 결정

`bot_snapshots` 테이블에 주기적 스냅샷(기본 1시간 간격)을 저장합니다.

**이유:** TimescaleDB 확장은 인프라 복잡도 증가, 실시간 계산은 조회 시 부하 증가. 스냅샷 방식이 1인 MVP에 가장 현실적이며, 추후 데이터가 쌓이면 TimescaleDB로 마이그레이션 가능.

### 1.4 소셜 로그인

MVP에서 **이메일/비밀번호 전용**으로 구현. `users` 테이블에 `oauth_provider`, `oauth_id` 컬럼을 미리 추가해두어 Phase 2 소셜 로그인 확장 시 마이그레이션 불필요.

---

## 2. ERD 다이어그램 (텍스트)

```
[users] 1 ──── N [exchange_accounts]
[users] 1 ──── N [user_sessions]
[users] 1 ──── 1 [subscriptions] N ──── 1 [subscription_plans]
[users] 1 ──── N [payment_history]
[users] 1 ──── N [bots]
  [bots] 1 ──── 1 [bot_config_grid]
  [bots] 1 ──── 1 [bot_config_snowball]
  [bots] 1 ──── 1 [bot_config_rebalancing] 1 ──── N [bot_config_rebal_assets]
  [bots] 1 ──── 1 [bot_config_dca]
  [bots] 1 ──── 1 [bot_config_algo]
  [bots] 1 ──── N [bot_orders] 1 ──── N [bot_trades]
  [bots] 1 ──── N [bot_snapshots]
  [bots] 1 ──── N [bot_logs]
[users] 1 ──── N [notifications]
[users] 1 ──── 1 [notification_settings]
[announcements] (독립)
```

---

## 3. 테이블 목록 및 역할 (총 20개)

| 테이블 | 역할 | 주요 관계 |
|--------|------|-----------|
| `users` | 사용자 계정 | 최상위 엔티티 |
| `user_sessions` | Refresh Token 관리 | users 1:N |
| `exchange_accounts` | 거래소/증권사 API 계좌 연동 | users 1:N |
| `subscription_plans` | 구독 플랜 정의 (마스터 데이터) | |
| `subscriptions` | 사용자별 구독 현황 | users 1:1 활성 |
| `payment_history` | 결제 내역 | users 1:N |
| `bots` | 봇 공통 정보 및 상태 | users 1:N |
| `bot_config_grid` | Spot Grid 봇 전용 파라미터 | bots 1:1 |
| `bot_config_snowball` | Position Snowball 봇 전용 파라미터 | bots 1:1 |
| `bot_config_rebalancing` | Rebalancing 봇 전용 파라미터 | bots 1:1 |
| `bot_config_rebal_assets` | 리밸런싱 자산 목록 | bot_config_rebalancing 1:N |
| `bot_config_dca` | Spot DCA 봇 전용 파라미터 | bots 1:1 |
| `bot_config_algo` | Algo Orders 봇 전용 파라미터 | bots 1:1 |
| `bot_orders` | 봇이 발행한 주문 내역 | bots 1:N |
| `bot_trades` | 주문 체결 내역 | bot_orders 1:N |
| `bot_snapshots` | 봇 수익/자산 시계열 스냅샷 (1시간 간격) | bots 1:N |
| `bot_logs` | 봇 실행 이벤트 로그 | bots 1:N |
| `notifications` | 발송된 알림 내역 | users 1:N |
| `notification_settings` | 사용자별 알림 수신 설정 | users 1:1 |
| `announcements` | 시스템 공지사항 (관리자 작성) | 독립 |

---

## 4. 테이블 상세 정의

> **표기 규칙**  
> `PK` = Primary Key / `FK` = Foreign Key / `UQ` = Unique / `IDX` = Index  
> `NN` = NOT NULL / `DEF` = Default

---

### 4.1 `users` — 사용자 계정

| 컬럼명 | 타입 | 제약 | 설명 |
|--------|------|------|------|
| `id` | `UUID` | PK, DEF `gen_random_uuid()` | 사용자 고유 ID |
| `email` | `VARCHAR(255)` | UQ, NN | 로그인 이메일 |
| `password_hash` | `VARCHAR(255)` | | bcrypt 해시. 소셜 전용 계정은 NULL |
| `display_name` | `VARCHAR(100)` | NN | 표시 이름 |
| `profile_image_url` | `TEXT` | | 프로필 이미지 URL |
| `is_email_verified` | `BOOLEAN` | NN, DEF `false` | 이메일 인증 완료 여부 |
| `is_active` | `BOOLEAN` | NN, DEF `true` | 계정 활성 상태 (관리자 정지 시 false) |
| `totp_secret` | `VARCHAR(64)` | | 2FA TOTP 시크릿 (암호화 저장). NULL이면 2FA 미설정 |
| `totp_enabled` | `BOOLEAN` | NN, DEF `false` | 2FA 활성화 여부 |
| `failed_login_count` | `SMALLINT` | NN, DEF `0` | 연속 로그인 실패 횟수 (5회 초과 시 잠금) |
| `locked_until` | `TIMESTAMPTZ` | | 계정 잠금 해제 시각 |
| `oauth_provider` | `VARCHAR(20)` | | 소셜 제공자 (google, kakao). Phase 2 용 |
| `oauth_id` | `VARCHAR(255)` | | 소셜 제공자의 사용자 ID. Phase 2 용 |
| `role` | `user_role` (ENUM) | NN, DEF `'user'` | 역할 (user, admin) |
| `created_at` | `TIMESTAMPTZ` | NN, DEF `now()` | 가입 일시 |
| `updated_at` | `TIMESTAMPTZ` | NN, DEF `now()` | 마지막 수정 일시 |
| `deleted_at` | `TIMESTAMPTZ` | | 탈퇴 일시 (Soft Delete) |

**인덱스:**
- `IDX users_email` on `(email)` WHERE `deleted_at IS NULL`
- `IDX users_oauth` on `(oauth_provider, oauth_id)` WHERE `oauth_provider IS NOT NULL`

---

### 4.2 `user_sessions` — Refresh Token 관리

| 컬럼명 | 타입 | 제약 | 설명 |
|--------|------|------|------|
| `id` | `UUID` | PK | 세션 고유 ID |
| `user_id` | `UUID` | FK→users.id, NN | 사용자 |
| `refresh_token_hash` | `VARCHAR(255)` | UQ, NN | Refresh Token의 SHA-256 해시 |
| `ip_address` | `INET` | | 발급 IP |
| `user_agent` | `TEXT` | | 클라이언트 User-Agent |
| `expires_at` | `TIMESTAMPTZ` | NN | 만료 일시 (발급 후 14일) |
| `created_at` | `TIMESTAMPTZ` | NN, DEF `now()` | 발급 일시 |
| `revoked_at` | `TIMESTAMPTZ` | | 명시적 로그아웃 일시 |

**설계 메모:** Access Token(1시간)은 DB에 저장하지 않고 JWT 자체 검증. Refresh Token만 해시로 저장하여 탈취 시 무효화 가능.

---

### 4.3 `exchange_accounts` — 거래소 API 계좌 연동

| 컬럼명 | 타입 | 제약 | 설명 |
|--------|------|------|------|
| `id` | `UUID` | PK | 계좌 고유 ID |
| `user_id` | `UUID` | FK→users.id, NN | 소유 사용자 |
| `exchange` | `exchange_type` (ENUM) | NN | binance, upbit, kis, kiwoom |
| `label` | `VARCHAR(100)` | NN | 사용자 지정 이름 (예: "내 바이낸스 계좌") |
| `api_key_enc` | `TEXT` | NN | AES-256-GCM 암호화된 API Key |
| `api_secret_enc` | `TEXT` | NN | AES-256-GCM 암호화된 API Secret |
| `extra_params_enc` | `TEXT` | | 추가 파라미터 암호화 JSON (KIS: 계좌번호 등) |
| `is_active` | `BOOLEAN` | NN, DEF `true` | 연동 활성 여부 |
| `is_valid` | `BOOLEAN` | NN, DEF `false` | API Key 유효성 검증 통과 여부 |
| `last_verified_at` | `TIMESTAMPTZ` | | 마지막 유효성 검증 일시 |
| `created_at` | `TIMESTAMPTZ` | NN, DEF `now()` | 등록 일시 |
| `updated_at` | `TIMESTAMPTZ` | NN, DEF `now()` | 수정 일시 |
| `deleted_at` | `TIMESTAMPTZ` | | 삭제 일시 (Soft Delete) |

**설계 메모:** `extra_params_enc`는 KIS의 계좌번호(`CANO`), 상품코드(`ACNT_PRDT_CD`), 키움의 계좌번호 등 거래소별 추가 정보를 암호화된 JSON으로 저장.

---

### 4.4 `subscription_plans` — 구독 플랜 (마스터 데이터)

| 컬럼명 | 타입 | 제약 | 설명 |
|--------|------|------|------|
| `id` | `UUID` | PK | |
| `name` | `VARCHAR(50)` | UQ, NN | 플랜 코드 (free, basic, pro, enterprise) |
| `display_name` | `VARCHAR(100)` | NN | 표시 이름 |
| `price_krw` | `INTEGER` | NN | 월 가격 (원 단위, Free=0) |
| `max_bots` | `SMALLINT` | NN | 최대 동시 운영 봇 수 (-1이면 무제한) |
| `max_accounts` | `SMALLINT` | NN | 최대 연동 계좌 수 |
| `features` | `JSONB` | NN, DEF `'{}'` | 기능 플래그 (예: `{"advanced_analytics": true}`) |
| `is_active` | `BOOLEAN` | NN, DEF `true` | 판매 활성 여부 |
| `created_at` | `TIMESTAMPTZ` | NN, DEF `now()` | |

**초기 데이터 (seed):**

| name | price_krw | max_bots | max_accounts |
|------|-----------|----------|--------------|
| free | 0 | 1 | 1 |
| basic | 9900 | 5 | 2 |
| pro | 29900 | -1 | 4 |
| enterprise | 0 (별도협의) | -1 | -1 |

---

### 4.5 `subscriptions` — 사용자별 구독 현황

| 컬럼명 | 타입 | 제약 | 설명 |
|--------|------|------|------|
| `id` | `UUID` | PK | |
| `user_id` | `UUID` | FK→users.id, UQ, NN | 1명당 활성 구독 1개 |
| `plan_id` | `UUID` | FK→subscription_plans.id, NN | 현재 플랜 |
| `status` | `subscription_status` (ENUM) | NN | active, cancelled, expired, past_due |
| `pg_subscription_id` | `VARCHAR(255)` | | PG사 구독 ID (자동결제 관리) |
| `started_at` | `TIMESTAMPTZ` | NN | 구독 시작 일시 |
| `expires_at` | `TIMESTAMPTZ` | | 구독 만료 일시 (null이면 무기한) |
| `cancelled_at` | `TIMESTAMPTZ` | | 취소 일시 |
| `created_at` | `TIMESTAMPTZ` | NN, DEF `now()` | |
| `updated_at` | `TIMESTAMPTZ` | NN, DEF `now()` | |

---

### 4.6 `payment_history` — 결제 내역

| 컬럼명 | 타입 | 제약 | 설명 |
|--------|------|------|------|
| `id` | `UUID` | PK | |
| `user_id` | `UUID` | FK→users.id, NN | |
| `subscription_id` | `UUID` | FK→subscriptions.id | |
| `plan_id` | `UUID` | FK→subscription_plans.id, NN | 결제 당시 플랜 |
| `amount_krw` | `INTEGER` | NN | 결제 금액 (원) |
| `status` | `payment_status` (ENUM) | NN | paid, failed, refunded |
| `pg_provider` | `VARCHAR(50)` | | PG사 이름 |
| `pg_payment_id` | `VARCHAR(255)` | UQ | PG사 결제 ID |
| `paid_at` | `TIMESTAMPTZ` | | 결제 완료 일시 |
| `created_at` | `TIMESTAMPTZ` | NN, DEF `now()` | |

---

### 4.7 `bots` — 봇 공통 정보 및 상태

| 컬럼명 | 타입 | 제약 | 설명 |
|--------|------|------|------|
| `id` | `UUID` | PK | |
| `user_id` | `UUID` | FK→users.id, NN | |
| `account_id` | `UUID` | FK→exchange_accounts.id, NN | |
| `bot_type` | `bot_type` (ENUM) | NN | spot_grid, position_snowball, rebalancing, spot_dca, algo_orders |
| `name` | `VARCHAR(100)` | NN | 사용자 지정 봇 이름 |
| `status` | `bot_status` (ENUM) | NN, DEF `'stopped'` | stopped, pending, running, error, completed |
| `symbol` | `VARCHAR(30)` | | 거래 심볼 (Rebalancing은 NULL) |
| `base_currency` | `VARCHAR(20)` | | 기준 통화 (예: BTC) |
| `quote_currency` | `VARCHAR(20)` | | 견적 통화 (예: USDT, KRW) |
| `investment_amount` | `NUMERIC(36,18)` | NN, DEF `0` | 초기 투자 금액 |
| `stop_loss_pct` | `NUMERIC(10,4)` | | 손절 기준 (%). NULL이면 손절 없음 |
| `take_profit_pct` | `NUMERIC(10,4)` | | 목표 수익 기준 (%). NULL이면 자동 종료 없음 |
| `total_pnl` | `NUMERIC(36,18)` | NN, DEF `0` | 누적 실현 수익금 |
| `total_pnl_pct` | `NUMERIC(10,4)` | NN, DEF `0` | 누적 수익률 (%) |
| `total_fee` | `NUMERIC(36,18)` | NN, DEF `0` | 누적 수수료 |
| `error_message` | `TEXT` | | 마지막 오류 메시지 |
| `celery_task_id` | `VARCHAR(255)` | | 실행 중인 Celery Task ID |
| `started_at` | `TIMESTAMPTZ` | | 가장 최근 시작 일시 |
| `stopped_at` | `TIMESTAMPTZ` | | 가장 최근 중지 일시 |
| `created_at` | `TIMESTAMPTZ` | NN, DEF `now()` | |
| `updated_at` | `TIMESTAMPTZ` | NN, DEF `now()` | |
| `deleted_at` | `TIMESTAMPTZ` | | 삭제 일시 (Soft Delete) |

**인덱스:**
- `IDX bots_user_status` on `(user_id, status)` WHERE `deleted_at IS NULL`
- `IDX bots_account` on `(account_id)` WHERE `deleted_at IS NULL`

---

### 4.8 `bot_config_grid` — Spot Grid 봇 설정

| 컬럼명 | 타입 | 제약 | 설명 |
|--------|------|------|------|
| `bot_id` | `UUID` | PK, FK→bots.id | |
| `upper_price` | `NUMERIC(36,18)` | NN | 상한가 |
| `lower_price` | `NUMERIC(36,18)` | NN | 하한가 |
| `grid_count` | `SMALLINT` | NN | 그리드 수 (2~200) |
| `grid_type` | `grid_type` (ENUM) | NN | arithmetic, geometric |
| `quantity_per_grid` | `NUMERIC(36,18)` | NN | 그리드당 주문 수량 |
| `created_at` | `TIMESTAMPTZ` | NN, DEF `now()` | |
| `updated_at` | `TIMESTAMPTZ` | NN, DEF `now()` | |

**제약:** `CHECK (upper_price > lower_price)`, `CHECK (grid_count BETWEEN 2 AND 200)`

---

### 4.9 `bot_config_snowball` — Position Snowball 봇 설정

| 컬럼명 | 타입 | 제약 | 설명 |
|--------|------|------|------|
| `bot_id` | `UUID` | PK, FK→bots.id | |
| `initial_amount` | `NUMERIC(36,18)` | NN | 초기 매수 금액 |
| `drop_trigger_pct` | `NUMERIC(10,4)` | NN | 추가 매수 트리거 하락률 (%) |
| `max_layers` | `SMALLINT` | NN | 최대 추가 매수 횟수 |
| `multiplier` | `NUMERIC(10,4)` | NN, DEF `1` | 추가 매수 금액 배수 |
| `take_profit_pct` | `NUMERIC(10,4)` | NN | 목표 수익률 (%) |
| `current_layer` | `SMALLINT` | NN, DEF `0` | 현재 누적 매수 레이어 수 (실행 중 업데이트) |
| `avg_entry_price` | `NUMERIC(36,18)` | | 현재 평균 매입 단가 |
| `total_invested` | `NUMERIC(36,18)` | NN, DEF `0` | 현재 총 투자금 |
| `created_at` | `TIMESTAMPTZ` | NN, DEF `now()` | |
| `updated_at` | `TIMESTAMPTZ` | NN, DEF `now()` | |

---

### 4.10 `bot_config_rebalancing` — Rebalancing 봇 설정

| 컬럼명 | 타입 | 제약 | 설명 |
|--------|------|------|------|
| `bot_id` | `UUID` | PK, FK→bots.id | |
| `rebal_mode` | `rebal_mode` (ENUM) | NN | time_based, deviation_based |
| `interval_unit` | `rebal_interval` (ENUM) | | daily, weekly, monthly (time_based일 때) |
| `interval_value` | `SMALLINT` | | 주기 값 (예: 2 = 2주마다) |
| `deviation_threshold_pct` | `NUMERIC(10,4)` | | 편차 임계값 (%) (deviation_based일 때) |
| `last_rebalanced_at` | `TIMESTAMPTZ` | | 마지막 리밸런싱 실행 일시 |
| `created_at` | `TIMESTAMPTZ` | NN, DEF `now()` | |
| `updated_at` | `TIMESTAMPTZ` | NN, DEF `now()` | |

---

### 4.11 `bot_config_rebal_assets` — 리밸런싱 자산 목록

| 컬럼명 | 타입 | 제약 | 설명 |
|--------|------|------|------|
| `id` | `UUID` | PK | |
| `bot_id` | `UUID` | FK→bots.id, NN | |
| `asset_symbol` | `VARCHAR(20)` | NN | 자산 심볼 (예: BTC, ETH) |
| `target_weight_pct` | `NUMERIC(10,4)` | NN | 목표 비중 (%). 해당 봇 자산 합계 = 100 |
| `current_weight_pct` | `NUMERIC(10,4)` | | 현재 실제 비중 (%). 주기적 업데이트 |
| `created_at` | `TIMESTAMPTZ` | NN, DEF `now()` | |

**제약:** `CHECK (target_weight_pct > 0 AND target_weight_pct <= 100)`  
**UQ:** `(bot_id, asset_symbol)`

---

### 4.12 `bot_config_dca` — Spot DCA 봇 설정

| 컬럼명 | 타입 | 제약 | 설명 |
|--------|------|------|------|
| `bot_id` | `UUID` | PK, FK→bots.id | |
| `order_amount` | `NUMERIC(36,18)` | NN | 1회 매수 금액 |
| `interval_unit` | `dca_interval` (ENUM) | NN | hourly, daily, weekly, monthly |
| `interval_value` | `SMALLINT` | NN, DEF `1` | 주기 값 |
| `total_orders` | `SMALLINT` | | 총 실행 횟수 제한. NULL이면 무기한 |
| `executed_orders` | `SMALLINT` | NN, DEF `0` | 현재까지 실행된 횟수 |
| `avg_entry_price` | `NUMERIC(36,18)` | | 현재 평균 매입 단가 |
| `next_execute_at` | `TIMESTAMPTZ` | | 다음 매수 예정 일시 |
| `created_at` | `TIMESTAMPTZ` | NN, DEF `now()` | |
| `updated_at` | `TIMESTAMPTZ` | NN, DEF `now()` | |

---

### 4.13 `bot_config_algo` — Spot Algo Orders 봇 설정

| 컬럼명 | 타입 | 제약 | 설명 |
|--------|------|------|------|
| `bot_id` | `UUID` | PK, FK→bots.id | |
| `order_side` | `order_side` (ENUM) | NN | buy, sell |
| `total_quantity` | `NUMERIC(36,18)` | | 총 수량 기준 (금액 기준이면 NULL) |
| `total_amount` | `NUMERIC(36,18)` | | 총 금액 기준 (수량 기준이면 NULL) |
| `algo_type` | `algo_type` (ENUM) | NN | twap |
| `execute_start_at` | `TIMESTAMPTZ` | NN | 실행 시작 시각 |
| `execute_end_at` | `TIMESTAMPTZ` | NN | 실행 종료 시각 |
| `split_count` | `SMALLINT` | NN | 분할 횟수 |
| `executed_count` | `SMALLINT` | NN, DEF `0` | 현재까지 실행된 분할 횟수 |
| `avg_fill_price` | `NUMERIC(36,18)` | | 현재 평균 체결가 |
| `created_at` | `TIMESTAMPTZ` | NN, DEF `now()` | |
| `updated_at` | `TIMESTAMPTZ` | NN, DEF `now()` | |

**제약:**
- `CHECK (execute_end_at > execute_start_at)`
- `CHECK (total_quantity IS NOT NULL OR total_amount IS NOT NULL)`

---

### 4.14 `bot_orders` — 봇이 발행한 주문

| 컬럼명 | 타입 | 제약 | 설명 |
|--------|------|------|------|
| `id` | `UUID` | PK | |
| `bot_id` | `UUID` | FK→bots.id, NN | |
| `exchange_order_id` | `VARCHAR(100)` | NN | 거래소 부여 주문 ID |
| `side` | `order_side` (ENUM) | NN | buy, sell |
| `order_type` | `order_type` (ENUM) | NN | limit, market, stop_limit |
| `status` | `order_status` (ENUM) | NN | pending, open, filled, partially_filled, cancelled, rejected |
| `symbol` | `VARCHAR(30)` | NN | 거래 심볼 |
| `price` | `NUMERIC(36,18)` | | 주문 가격 (market은 NULL) |
| `quantity` | `NUMERIC(36,18)` | NN | 주문 수량 |
| `filled_quantity` | `NUMERIC(36,18)` | NN, DEF `0` | 체결된 수량 |
| `avg_fill_price` | `NUMERIC(36,18)` | | 평균 체결가 |
| `fee` | `NUMERIC(36,18)` | NN, DEF `0` | 수수료 |
| `fee_currency` | `VARCHAR(20)` | | 수수료 통화 |
| `grid_level` | `SMALLINT` | | Grid 봇 전용: 해당 그리드 레벨 |
| `layer_index` | `SMALLINT` | | Snowball 봇 전용: 해당 레이어 인덱스 |
| `placed_at` | `TIMESTAMPTZ` | NN | 거래소 주문 발행 일시 |
| `filled_at` | `TIMESTAMPTZ` | | 완전 체결 일시 |
| `created_at` | `TIMESTAMPTZ` | NN, DEF `now()` | |
| `updated_at` | `TIMESTAMPTZ` | NN, DEF `now()` | |

**인덱스:**
- `IDX bo_bot_status` on `(bot_id, status)`
- `IDX bo_exchange_order` on `(exchange_order_id)` — 체결 콜백 처리용
- `IDX bo_placed_at` on `(bot_id, placed_at DESC)` — 최근 주문 조회용

---

### 4.15 `bot_trades` — 주문 체결 내역

| 컬럼명 | 타입 | 제약 | 설명 |
|--------|------|------|------|
| `id` | `UUID` | PK | |
| `order_id` | `UUID` | FK→bot_orders.id, NN | |
| `bot_id` | `UUID` | FK→bots.id, NN | 조회 편의를 위한 역참조 |
| `exchange_trade_id` | `VARCHAR(100)` | | 거래소 체결 ID |
| `price` | `NUMERIC(36,18)` | NN | 체결 가격 |
| `quantity` | `NUMERIC(36,18)` | NN | 체결 수량 |
| `fee` | `NUMERIC(36,18)` | NN, DEF `0` | 체결 수수료 |
| `fee_currency` | `VARCHAR(20)` | | |
| `is_maker` | `BOOLEAN` | | 메이커 여부 |
| `traded_at` | `TIMESTAMPTZ` | NN | 거래소 체결 일시 |
| `created_at` | `TIMESTAMPTZ` | NN, DEF `now()` | |

**인덱스:**
- `IDX bt_bot_traded` on `(bot_id, traded_at DESC)`

---

### 4.16 `bot_snapshots` — 봇 수익 시계열 스냅샷

봇 운영 중 1시간 간격으로 수익 상태를 기록. 수익 차트의 데이터 소스.

| 컬럼명 | 타입 | 제약 | 설명 |
|--------|------|------|------|
| `id` | `UUID` | PK | |
| `bot_id` | `UUID` | FK→bots.id, NN | |
| `snapshot_at` | `TIMESTAMPTZ` | NN | 스냅샷 기록 일시 |
| `total_pnl` | `NUMERIC(36,18)` | NN | 누적 수익금 (스냅샷 시점) |
| `total_pnl_pct` | `NUMERIC(10,4)` | NN | 누적 수익률 (%) |
| `portfolio_value` | `NUMERIC(36,18)` | NN | 현재 평가 자산 (투자금 + 미실현 수익) |
| `created_at` | `TIMESTAMPTZ` | NN, DEF `now()` | |

**인덱스:**
- `IDX bs_bot_time` on `(bot_id, snapshot_at DESC)`

---

### 4.17 `bot_logs` — 봇 실행 이벤트 로그

| 컬럼명 | 타입 | 제약 | 설명 |
|--------|------|------|------|
| `id` | `UUID` | PK | |
| `bot_id` | `UUID` | FK→bots.id, NN | |
| `level` | `log_level` (ENUM) | NN | info, warning, error |
| `event_type` | `VARCHAR(50)` | NN | bot_started, order_placed, order_filled, stop_loss_triggered, error 등 |
| `message` | `TEXT` | NN | 로그 메시지 |
| `metadata` | `JSONB` | DEF `'{}'` | 추가 컨텍스트 (주문 ID, 가격 등) |
| `created_at` | `TIMESTAMPTZ` | NN, DEF `now()` | |

**인덱스:**
- `IDX bl_bot_created` on `(bot_id, created_at DESC)`
- `IDX bl_error` on `(bot_id, level)` WHERE `level = 'error'`

---

### 4.18 `notifications` — 발송된 알림 내역

| 컬럼명 | 타입 | 제약 | 설명 |
|--------|------|------|------|
| `id` | `UUID` | PK | |
| `user_id` | `UUID` | FK→users.id, NN | |
| `bot_id` | `UUID` | FK→bots.id | 관련 봇 (NULL이면 시스템 알림) |
| `channel` | `notify_channel` (ENUM) | NN | email, telegram, web_push |
| `event_type` | `VARCHAR(50)` | NN | bot_started, bot_stopped, bot_error, take_profit, stop_loss 등 |
| `title` | `VARCHAR(255)` | NN | 알림 제목 |
| `body` | `TEXT` | NN | 알림 본문 |
| `is_read` | `BOOLEAN` | NN, DEF `false` | 웹 알림 읽음 여부 |
| `sent_at` | `TIMESTAMPTZ` | | 실제 발송 완료 일시 |
| `failed_at` | `TIMESTAMPTZ` | | 발송 실패 일시 |
| `created_at` | `TIMESTAMPTZ` | NN, DEF `now()` | |

**인덱스:**
- `IDX noti_user_unread` on `(user_id, is_read)` WHERE `is_read = false`

---

### 4.19 `notification_settings` — 사용자별 알림 수신 설정

| 컬럼명 | 타입 | 제약 | 설명 |
|--------|------|------|------|
| `user_id` | `UUID` | PK, FK→users.id | users와 1:1 |
| `email_enabled` | `BOOLEAN` | NN, DEF `true` | 이메일 알림 전체 ON/OFF |
| `telegram_enabled` | `BOOLEAN` | NN, DEF `false` | 텔레그램 알림 전체 ON/OFF |
| `telegram_chat_id` | `VARCHAR(100)` | | 텔레그램 Chat ID |
| `notify_bot_start` | `BOOLEAN` | NN, DEF `true` | |
| `notify_bot_stop` | `BOOLEAN` | NN, DEF `true` | |
| `notify_bot_error` | `BOOLEAN` | NN, DEF `true` | |
| `notify_take_profit` | `BOOLEAN` | NN, DEF `true` | |
| `notify_stop_loss` | `BOOLEAN` | NN, DEF `true` | |
| `updated_at` | `TIMESTAMPTZ` | NN, DEF `now()` | |

---

### 4.20 `announcements` — 시스템 공지사항

| 컬럼명 | 타입 | 제약 | 설명 |
|--------|------|------|------|
| `id` | `UUID` | PK | |
| `title` | `VARCHAR(255)` | NN | 공지 제목 |
| `content` | `TEXT` | NN | 공지 내용 (Markdown 지원) |
| `is_pinned` | `BOOLEAN` | NN, DEF `false` | 상단 고정 여부 |
| `is_published` | `BOOLEAN` | NN, DEF `false` | 게시 여부 |
| `published_at` | `TIMESTAMPTZ` | | 게시 일시 |
| `created_by` | `UUID` | FK→users.id, NN | 작성 관리자 |
| `created_at` | `TIMESTAMPTZ` | NN, DEF `now()` | |
| `updated_at` | `TIMESTAMPTZ` | NN, DEF `now()` | |

---

## 5. 인덱스 전략

### 5.1 핵심 조회 패턴별 인덱스 요약

| 조회 패턴 | 테이블 | 인덱스 컬럼 |
|-----------|--------|------------|
| 로그인 시 이메일 조회 | `users` | `(email)` WHERE `deleted_at IS NULL` |
| 사용자의 활성 봇 목록 | `bots` | `(user_id, status)` WHERE `deleted_at IS NULL` |
| 봇의 최근 주문 조회 | `bot_orders` | `(bot_id, placed_at DESC)` |
| 거래소 주문 ID로 체결 반영 | `bot_orders` | `(exchange_order_id)` |
| 봇 수익 차트용 스냅샷 조회 | `bot_snapshots` | `(bot_id, snapshot_at DESC)` |
| 봇 오류 로그만 필터링 | `bot_logs` | `(bot_id, level)` WHERE `level = 'error'` |
| 사용자 미읽은 알림 목록 | `notifications` | `(user_id, is_read)` WHERE `is_read = false` |

### 5.2 인덱스 주의사항

쓰기가 빈번한 `bot_orders`, `bot_trades`, `bot_snapshots`는 인덱스를 최소화하여 삽입 성능 유지. `JSONB` 컬럼(`metadata`, `features`)에 대한 GIN 인덱스는 실제 조회 필요성 확인 후 추가.

---

## 6. 파티셔닝 전략

### 6.1 MVP 단계

파티셔닝 없이 운영. 초기 데이터 볼륨에서는 오버엔지니어링.

### 6.2 스케일 업 기준 (사용자 10,000명 이상)

| 테이블 | 파티셔닝 방식 | 기준 컬럼 |
|--------|-------------|----------|
| `bot_snapshots` | Range | `snapshot_at` 월별 |
| `bot_logs` | Range | `created_at` 월별 |
| `bot_trades` | Range | `traded_at` 월별 |

PostgreSQL 선언적 파티셔닝으로 전환 시 Alembic 마이그레이션으로 처리 가능.

---

## 7. Enum 타입 정의

```sql
-- 사용자 역할
CREATE TYPE user_role AS ENUM ('user', 'admin');

-- 거래소 종류
CREATE TYPE exchange_type AS ENUM ('binance', 'upbit', 'kis', 'kiwoom');

-- 구독 상태
CREATE TYPE subscription_status AS ENUM ('active', 'cancelled', 'expired', 'past_due');

-- 결제 상태
CREATE TYPE payment_status AS ENUM ('paid', 'failed', 'refunded');

-- 봇 타입
CREATE TYPE bot_type AS ENUM (
    'spot_grid', 'position_snowball', 'rebalancing', 'spot_dca', 'algo_orders'
);

-- 봇 상태
CREATE TYPE bot_status AS ENUM (
    'stopped',    -- 중지 (초기값, 수동 중지)
    'pending',    -- 시작 명령 후 Worker 수신 대기
    'running',    -- 정상 실행 중
    'error',      -- 오류로 인한 비정상 중지
    'completed'   -- 목표 달성 또는 기간 완료로 인한 정상 종료
);

-- 그리드 타입
CREATE TYPE grid_type AS ENUM ('arithmetic', 'geometric');

-- 리밸런싱 모드 및 주기
CREATE TYPE rebal_mode AS ENUM ('time_based', 'deviation_based');
CREATE TYPE rebal_interval AS ENUM ('daily', 'weekly', 'monthly');

-- DCA 주기
CREATE TYPE dca_interval AS ENUM ('hourly', 'daily', 'weekly', 'monthly');

-- 알고 주문 타입
CREATE TYPE algo_type AS ENUM ('twap');

-- 주문 방향 / 타입 / 상태
CREATE TYPE order_side AS ENUM ('buy', 'sell');
CREATE TYPE order_type AS ENUM ('limit', 'market', 'stop_limit');
CREATE TYPE order_status AS ENUM (
    'pending', 'open', 'filled', 'partially_filled', 'cancelled', 'rejected'
);

-- 로그 레벨
CREATE TYPE log_level AS ENUM ('info', 'warning', 'error');

-- 알림 채널
CREATE TYPE notify_channel AS ENUM ('email', 'telegram', 'web_push');
```

---

## 8. 공통 컬럼 규칙

### 8.1 네이밍 컨벤션

| 규칙 | 예시 |
|------|------|
| 테이블명: `snake_case` 복수형 | `exchange_accounts`, `bot_orders` |
| 컬럼명: `snake_case` | `created_at`, `user_id` |
| FK 컬럼: `{참조테이블단수}_id` | `user_id`, `bot_id`, `plan_id` |
| Boolean: `is_` 또는 `has_` 접두사 | `is_active`, `is_valid` |
| 일시: `_at` 접미사 | `created_at`, `deleted_at` |
| 퍼센트: `_pct` 접미사 | `pnl_pct`, `target_weight_pct` |
| 암호화 값: `_enc` 접미사 | `api_key_enc`, `api_secret_enc` |

### 8.2 Soft Delete 적용 대상

Soft Delete(`deleted_at`) 적용 테이블: `users`, `exchange_accounts`, `bots`

나머지 테이블(orders, trades, logs 등)은 Hard Delete. 단, 거래 내역(`bot_trades`, `bot_orders`)은 법적 요건상 최소 1년 보관 필요.

### 8.3 updated_at 자동 갱신 (PostgreSQL Trigger)

```sql
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = now();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- 각 테이블에 적용 (예시)
CREATE TRIGGER trg_users_updated_at
    BEFORE UPDATE ON users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();
```

> SQLAlchemy에서는 `onupdate=func.now()` 옵션으로도 처리 가능하지만,
> DB 레벨 trigger를 함께 설정하면 ORM 외부 쿼리(배치 등)에서도 일관성 유지.

---

## 9. SQLModel 모델 매핑 가이드

> 이 프로젝트는 `fastapi/full-stack-fastapi-template`을 기반으로 합니다. 템플릿은 **SQLModel**을 사용하므로, 모든 모델은 SQLModel 패턴으로 작성합니다.

### 9.1 SQLModel 기본 패턴

SQLModel은 SQLAlchemy ORM 위에 Pydantic을 통합한 라이브러리입니다. `Base`, `Mixin` 클래스 대신 `SQLModel` 상속으로 ORM 모델과 API 스키마를 함께 정의합니다.

```python
# backend/app/models.py 에 추가하는 방식
import uuid
from datetime import datetime, timezone
from decimal import Decimal
from sqlalchemy import Column, Numeric, DateTime
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, Relationship, SQLModel


# ── 1. Base 클래스 (공통 필드) ─────────────────────────────────
class BotBase(SQLModel):
    name: str = Field(max_length=100)
    bot_type: str = Field(max_length=50)
    exchange: str = Field(max_length=50)
    symbol: str = Field(max_length=30)
    config: dict = Field(default={}, sa_column=Column(JSONB))


# ── 2. DB 테이블 모델 (table=True) ─────────────────────────────
class Bot(BotBase, table=True):
    id: uuid.UUID = Field(default_factory=uuid.uuid4, primary_key=True)
    user_id: uuid.UUID = Field(foreign_key="user.id", ondelete="CASCADE")
    account_id: uuid.UUID = Field(foreign_key="exchangeaccount.id")
    status: str = Field(default="stopped", max_length=20)
    celery_task_id: str | None = Field(default=None, max_length=255)
    total_profit: Decimal = Field(
        default=Decimal("0"),
        sa_column=Column(Numeric(precision=36, scale=18), nullable=False)
    )
    deleted_at: datetime | None = Field(
        default=None,
        sa_column=Column(DateTime(timezone=True), nullable=True)
    )
    created_at: datetime = Field(
        default_factory=lambda: datetime.now(timezone.utc),
        sa_column=Column(DateTime(timezone=True), nullable=False)
    )
    # 관계 정의
    owner: "User" = Relationship(back_populates="bots")
    orders: list["BotOrder"] = Relationship(back_populates="bot", cascade_delete=True)
    logs: list["BotLog"] = Relationship(back_populates="bot", cascade_delete=True)


# ── 3. API 요청 스키마 ──────────────────────────────────────────
class BotCreate(BotBase):
    account_id: uuid.UUID


# ── 4. API 응답 스키마 ──────────────────────────────────────────
class BotPublic(BotBase):
    id: uuid.UUID
    status: str
    total_profit: Decimal
    created_at: datetime


class BotsPublic(SQLModel):
    data: list[BotPublic]
    count: int


class BotUpdate(SQLModel):
    name: str | None = Field(default=None, max_length=100)
    config: dict | None = None
```

### 9.2 테이블명 규칙

SQLModel은 클래스명을 소문자로 변환하여 테이블명을 자동 결정합니다.

| 클래스명 | 자동 생성 테이블명 |
|---------|-----------------|
| `User` | `user` |
| `Bot` | `bot` |
| `ExchangeAccount` | `exchangeaccount` |
| `BotOrder` | `botorder` |
| `BotLog` | `botlog` |
| `BotSnapshot` | `botsnapshot` |
| `SubscriptionPlan` | `subscriptionplan` |
| `UserSubscription` | `usersubscription` |

> DB 설계서 섹션 1~7의 테이블명(`bots`, `exchange_accounts` 등)은 논리적 표현입니다. 실제 생성 테이블명은 위 규칙을 따릅니다. 필요시 `__tablename__`으로 명시할 수 있습니다.

### 9.3 JSONB 컬럼 사용

봇 설정(config), 거래소별 추가 파라미터 등 구조가 유동적인 데이터는 JSONB 컬럼에 저장합니다.

```python
from sqlalchemy import Column
from sqlalchemy.dialects.postgresql import JSONB
from sqlmodel import Field, SQLModel

class BotBase(SQLModel):
    config: dict = Field(
        default={},
        sa_column=Column(JSONB, nullable=False, server_default="{}")
    )
```

### 9.4 Soft Delete 패턴

```python
from sqlmodel import Session, select

# ── 소프트 삭제 ────────────────────────────────────────────────
def delete_bot(*, session: Session, bot: Bot) -> None:
    bot.deleted_at = datetime.now(timezone.utc)
    session.add(bot)
    session.commit()

# ── 조회 시 항상 deleted_at 조건 포함 ─────────────────────────
def get_bots_by_user(*, session: Session, user_id: uuid.UUID) -> list[Bot]:
    statement = select(Bot).where(
        Bot.user_id == user_id,
        Bot.deleted_at.is_(None)   # ← 반드시 포함
    )
    return list(session.exec(statement).all())

# ❌ 절대 금지 — 하드 삭제
session.delete(bot)

# ❌ 절대 금지 — deleted_at 조건 누락
select(Bot).where(Bot.user_id == user_id)
```

---

## 10. 변경 이력

| 버전 | 날짜 | 변경 내용 | 작성자 |
|------|------|-----------|--------|
| v1.0 | 2025년 | 최초 작성 — 20개 테이블 정의, UUID PK, Soft Delete, NUMERIC(36,18) 금융 정밀도, 봇 타입별 설정 테이블 분리 | PM |
| v1.1 | 2025년 | fastapi/full-stack-fastapi-template 기반 전환 — 섹션 9 "SQLAlchemy 모델 매핑 가이드"를 "SQLModel 모델 매핑 가이드"로 전면 교체. DeclarativeBase/Mapped 방식 → SQLModel(table=True) 방식으로 변경. SQLModel 테이블명 자동 생성 규칙, JSONB 컬럼, Soft Delete 패턴 SQLModel 문법으로 재작성 | PM |

---

*DB 구조 변경 시 반드시 Alembic 마이그레이션 파일과 함께 본 문서도 업데이트하세요.*
