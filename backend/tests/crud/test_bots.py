"""Bot CRUD 함수 단위 테스트.

DB 레이어를 직접 테스트합니다.
커버리지 목표: 80%+
"""
import uuid
from decimal import Decimal

from sqlmodel import Session

from app import crud
from app.models import (
    BotCreate,
    BotStatusEnum,
    BotTypeEnum,
    BotUpdate,
    ExchangeAccountCreate,
    ExchangeTypeEnum,
)
from tests.utils.user import create_random_user
from tests.utils.utils import random_lower_string


# ── 헬퍼 ──────────────────────────────────────────────────────────────────────


def _make_account(db: Session, user_id: uuid.UUID):
    """테스트용 거래소 계좌를 DB에 직접 생성."""
    account_in = ExchangeAccountCreate(
        exchange=ExchangeTypeEnum.binance,
        label=random_lower_string()[:20],
        api_key=random_lower_string(),
        api_secret=random_lower_string(),
    )
    return crud.create_exchange_account(
        session=db, account_in=account_in, owner_id=user_id
    )


def _bot_in(account_id: uuid.UUID, **overrides) -> BotCreate:
    data: dict = dict(
        name=random_lower_string()[:20],
        bot_type=BotTypeEnum.spot_dca,
        symbol="BTC/USDT",
        investment_amount=Decimal("100"),
        account_id=account_id,
    )
    data.update(overrides)
    return BotCreate(**data)


# ── create_bot ────────────────────────────────────────────────────────────────


class TestCreateBot:
    def test_create_bot_returns_model(self, db: Session) -> None:
        user = create_random_user(db)
        account = _make_account(db, user.id)
        bot = crud.create_bot(
            session=db, bot_in=_bot_in(account.id), owner_id=user.id
        )

        assert bot.id is not None
        assert bot.user_id == user.id
        assert bot.account_id == account.id

    def test_initial_status_is_stopped(self, db: Session) -> None:
        user = create_random_user(db)
        account = _make_account(db, user.id)
        bot = crud.create_bot(
            session=db, bot_in=_bot_in(account.id), owner_id=user.id
        )

        assert bot.status == BotStatusEnum.stopped

    def test_initial_pnl_is_zero(self, db: Session) -> None:
        user = create_random_user(db)
        account = _make_account(db, user.id)
        bot = crud.create_bot(
            session=db, bot_in=_bot_in(account.id), owner_id=user.id
        )

        assert bot.total_pnl == Decimal("0")
        assert bot.total_pnl_pct == Decimal("0")
        assert bot.total_fee == Decimal("0")

    def test_initial_deleted_at_none(self, db: Session) -> None:
        user = create_random_user(db)
        account = _make_account(db, user.id)
        bot = crud.create_bot(
            session=db, bot_in=_bot_in(account.id), owner_id=user.id
        )

        assert bot.deleted_at is None

    def test_bot_type_stored_correctly(self, db: Session) -> None:
        user = create_random_user(db)
        account = _make_account(db, user.id)

        for bot_type in BotTypeEnum:
            bot = crud.create_bot(
                session=db,
                bot_in=_bot_in(account.id, bot_type=bot_type),
                owner_id=user.id,
            )
            assert bot.bot_type == bot_type

    def test_timestamps_set_on_create(self, db: Session) -> None:
        user = create_random_user(db)
        account = _make_account(db, user.id)
        bot = crud.create_bot(
            session=db, bot_in=_bot_in(account.id), owner_id=user.id
        )

        assert bot.created_at is not None
        assert bot.updated_at is not None
        assert bot.started_at is None
        assert bot.stopped_at is None

    def test_investment_amount_stored_as_decimal(self, db: Session) -> None:
        user = create_random_user(db)
        account = _make_account(db, user.id)
        bot = crud.create_bot(
            session=db,
            bot_in=_bot_in(account.id, investment_amount=Decimal("999.5")),
            owner_id=user.id,
        )

        assert bot.investment_amount == Decimal("999.5")


# ── get_bot ───────────────────────────────────────────────────────────────────


class TestGetBot:
    def test_get_bot_returns_correct_record(self, db: Session) -> None:
        user = create_random_user(db)
        account = _make_account(db, user.id)
        bot = crud.create_bot(
            session=db, bot_in=_bot_in(account.id), owner_id=user.id
        )

        fetched = crud.get_bot(
            session=db, bot_id=bot.id, user_id=user.id
        )
        assert fetched is not None
        assert fetched.id == bot.id

    def test_get_bot_wrong_user_returns_none(self, db: Session) -> None:
        user1 = create_random_user(db)
        user2 = create_random_user(db)
        account = _make_account(db, user1.id)
        bot = crud.create_bot(
            session=db, bot_in=_bot_in(account.id), owner_id=user1.id
        )

        fetched = crud.get_bot(
            session=db, bot_id=bot.id, user_id=user2.id
        )
        assert fetched is None

    def test_get_nonexistent_bot_returns_none(self, db: Session) -> None:
        user = create_random_user(db)
        fetched = crud.get_bot(
            session=db, bot_id=uuid.uuid4(), user_id=user.id
        )
        assert fetched is None

    def test_get_soft_deleted_bot_returns_none(self, db: Session) -> None:
        user = create_random_user(db)
        account = _make_account(db, user.id)
        bot = crud.create_bot(
            session=db, bot_in=_bot_in(account.id), owner_id=user.id
        )
        crud.delete_bot(session=db, bot=bot)

        fetched = crud.get_bot(
            session=db, bot_id=bot.id, user_id=user.id
        )
        assert fetched is None


# ── get_bots_by_user ──────────────────────────────────────────────────────────


class TestGetBotsByUser:
    def test_returns_user_bots(self, db: Session) -> None:
        user = create_random_user(db)
        account = _make_account(db, user.id)
        crud.create_bot(
            session=db, bot_in=_bot_in(account.id), owner_id=user.id
        )
        crud.create_bot(
            session=db, bot_in=_bot_in(account.id), owner_id=user.id
        )

        bots = crud.get_bots_by_user(session=db, user_id=user.id)
        assert len(bots) == 2

    def test_excludes_other_users_bots(self, db: Session) -> None:
        user1 = create_random_user(db)
        user2 = create_random_user(db)
        account = _make_account(db, user1.id)
        crud.create_bot(
            session=db, bot_in=_bot_in(account.id), owner_id=user1.id
        )

        bots = crud.get_bots_by_user(session=db, user_id=user2.id)
        assert len(bots) == 0

    def test_excludes_soft_deleted_bots(self, db: Session) -> None:
        user = create_random_user(db)
        account = _make_account(db, user.id)
        bot = crud.create_bot(
            session=db, bot_in=_bot_in(account.id), owner_id=user.id
        )
        crud.delete_bot(session=db, bot=bot)

        bots = crud.get_bots_by_user(session=db, user_id=user.id)
        assert len(bots) == 0

    def test_pagination_skip(self, db: Session) -> None:
        user = create_random_user(db)
        account = _make_account(db, user.id)
        for _ in range(3):
            crud.create_bot(
                session=db, bot_in=_bot_in(account.id), owner_id=user.id
            )

        bots = crud.get_bots_by_user(session=db, user_id=user.id, skip=2)
        assert len(bots) == 1

    def test_pagination_limit(self, db: Session) -> None:
        user = create_random_user(db)
        account = _make_account(db, user.id)
        for _ in range(3):
            crud.create_bot(
                session=db, bot_in=_bot_in(account.id), owner_id=user.id
            )

        bots = crud.get_bots_by_user(session=db, user_id=user.id, limit=2)
        assert len(bots) == 2

    def test_empty_list_for_new_user(self, db: Session) -> None:
        user = create_random_user(db)
        bots = crud.get_bots_by_user(session=db, user_id=user.id)
        assert bots == []


# ── count_active_bots ─────────────────────────────────────────────────────────


class TestCountActiveBots:
    def test_count_active_bots(self, db: Session) -> None:
        user = create_random_user(db)
        account = _make_account(db, user.id)
        crud.create_bot(
            session=db, bot_in=_bot_in(account.id), owner_id=user.id
        )
        crud.create_bot(
            session=db, bot_in=_bot_in(account.id), owner_id=user.id
        )

        count = crud.count_active_bots(session=db, user_id=user.id)
        assert count == 2

    def test_count_excludes_deleted(self, db: Session) -> None:
        user = create_random_user(db)
        account = _make_account(db, user.id)
        bot = crud.create_bot(
            session=db, bot_in=_bot_in(account.id), owner_id=user.id
        )
        crud.delete_bot(session=db, bot=bot)

        count = crud.count_active_bots(session=db, user_id=user.id)
        assert count == 0

    def test_count_zero_for_new_user(self, db: Session) -> None:
        user = create_random_user(db)
        count = crud.count_active_bots(session=db, user_id=user.id)
        assert count == 0


# ── get_user_bot_limit ────────────────────────────────────────────────────────


class TestGetUserBotLimit:
    def test_no_subscription_returns_one(self, db: Session) -> None:
        """구독 없는 사용자는 기본 Free 한도(1)를 반환."""
        user = create_random_user(db)
        limit = crud.get_user_bot_limit(session=db, user_id=user.id)
        assert limit == 1


# ── update_bot ────────────────────────────────────────────────────────────────


class TestUpdateBot:
    def test_update_name(self, db: Session) -> None:
        user = create_random_user(db)
        account = _make_account(db, user.id)
        bot = crud.create_bot(
            session=db,
            bot_in=_bot_in(account.id, name="Old Name"),
            owner_id=user.id,
        )

        updated = crud.update_bot(
            session=db, bot=bot, bot_in=BotUpdate(name="New Name")
        )
        assert updated.name == "New Name"

    def test_update_stop_loss_pct(self, db: Session) -> None:
        user = create_random_user(db)
        account = _make_account(db, user.id)
        bot = crud.create_bot(
            session=db, bot_in=_bot_in(account.id), owner_id=user.id
        )

        updated = crud.update_bot(
            session=db,
            bot=bot,
            bot_in=BotUpdate(stop_loss_pct=Decimal("5.0")),
        )
        assert updated.stop_loss_pct == Decimal("5.0")

    def test_update_take_profit_pct(self, db: Session) -> None:
        user = create_random_user(db)
        account = _make_account(db, user.id)
        bot = crud.create_bot(
            session=db, bot_in=_bot_in(account.id), owner_id=user.id
        )

        updated = crud.update_bot(
            session=db,
            bot=bot,
            bot_in=BotUpdate(take_profit_pct=Decimal("10.5")),
        )
        assert updated.take_profit_pct == Decimal("10.5")

    def test_update_sets_updated_at(self, db: Session) -> None:
        user = create_random_user(db)
        account = _make_account(db, user.id)
        bot = crud.create_bot(
            session=db, bot_in=_bot_in(account.id), owner_id=user.id
        )
        original_updated_at = bot.updated_at

        updated = crud.update_bot(
            session=db, bot=bot, bot_in=BotUpdate(name="New Name")
        )
        assert updated.updated_at >= original_updated_at

    def test_partial_update_leaves_other_fields_unchanged(
        self, db: Session
    ) -> None:
        user = create_random_user(db)
        account = _make_account(db, user.id)
        original_bot_type = BotTypeEnum.spot_grid
        bot = crud.create_bot(
            session=db,
            bot_in=_bot_in(account.id, bot_type=original_bot_type),
            owner_id=user.id,
        )

        crud.update_bot(
            session=db, bot=bot, bot_in=BotUpdate(name="New Name")
        )

        assert bot.bot_type == original_bot_type


# ── delete_bot ────────────────────────────────────────────────────────────────


class TestDeleteBot:
    def test_delete_sets_deleted_at(self, db: Session) -> None:
        user = create_random_user(db)
        account = _make_account(db, user.id)
        bot = crud.create_bot(
            session=db, bot_in=_bot_in(account.id), owner_id=user.id
        )
        assert bot.deleted_at is None

        crud.delete_bot(session=db, bot=bot)
        assert bot.deleted_at is not None

    def test_deleted_bot_not_in_list(self, db: Session) -> None:
        user = create_random_user(db)
        account = _make_account(db, user.id)
        bot = crud.create_bot(
            session=db, bot_in=_bot_in(account.id), owner_id=user.id
        )
        crud.delete_bot(session=db, bot=bot)

        bots = crud.get_bots_by_user(session=db, user_id=user.id)
        assert bot.id not in [b.id for b in bots]

    def test_deleted_bot_not_fetchable_by_id(self, db: Session) -> None:
        user = create_random_user(db)
        account = _make_account(db, user.id)
        bot = crud.create_bot(
            session=db, bot_in=_bot_in(account.id), owner_id=user.id
        )
        crud.delete_bot(session=db, bot=bot)

        fetched = crud.get_bot(
            session=db, bot_id=bot.id, user_id=user.id
        )
        assert fetched is None


# ── start_bot ─────────────────────────────────────────────────────────────────


class TestStartBot:
    def test_start_bot_sets_status_pending(self, db: Session) -> None:
        user = create_random_user(db)
        account = _make_account(db, user.id)
        bot = crud.create_bot(
            session=db, bot_in=_bot_in(account.id), owner_id=user.id
        )
        assert bot.status == BotStatusEnum.stopped

        started = crud.start_bot(session=db, bot=bot)
        assert started.status == BotStatusEnum.pending

    def test_start_bot_sets_started_at(self, db: Session) -> None:
        user = create_random_user(db)
        account = _make_account(db, user.id)
        bot = crud.create_bot(
            session=db, bot_in=_bot_in(account.id), owner_id=user.id
        )
        assert bot.started_at is None

        started = crud.start_bot(session=db, bot=bot)
        assert started.started_at is not None

    def test_start_bot_sets_updated_at(self, db: Session) -> None:
        user = create_random_user(db)
        account = _make_account(db, user.id)
        bot = crud.create_bot(
            session=db, bot_in=_bot_in(account.id), owner_id=user.id
        )
        original_updated_at = bot.updated_at

        started = crud.start_bot(session=db, bot=bot)
        assert started.updated_at >= original_updated_at


# ── stop_bot ──────────────────────────────────────────────────────────────────


class TestStopBot:
    def test_stop_bot_sets_status_stopped(self, db: Session) -> None:
        user = create_random_user(db)
        account = _make_account(db, user.id)
        bot = crud.create_bot(
            session=db, bot_in=_bot_in(account.id), owner_id=user.id
        )
        crud.start_bot(session=db, bot=bot)
        assert bot.status == BotStatusEnum.pending

        stopped = crud.stop_bot(session=db, bot=bot)
        assert stopped.status == BotStatusEnum.stopped

    def test_stop_bot_sets_stopped_at(self, db: Session) -> None:
        user = create_random_user(db)
        account = _make_account(db, user.id)
        bot = crud.create_bot(
            session=db, bot_in=_bot_in(account.id), owner_id=user.id
        )
        crud.start_bot(session=db, bot=bot)
        assert bot.stopped_at is None

        stopped = crud.stop_bot(session=db, bot=bot)
        assert stopped.stopped_at is not None

    def test_stop_bot_sets_updated_at(self, db: Session) -> None:
        user = create_random_user(db)
        account = _make_account(db, user.id)
        bot = crud.create_bot(
            session=db, bot_in=_bot_in(account.id), owner_id=user.id
        )
        crud.start_bot(session=db, bot=bot)
        before_stop_updated_at = bot.updated_at

        stopped = crud.stop_bot(session=db, bot=bot)
        assert stopped.updated_at >= before_stop_updated_at

    def test_start_then_stop_cycle(self, db: Session) -> None:
        """stopped → pending → stopped 상태 순환 검증."""
        user = create_random_user(db)
        account = _make_account(db, user.id)
        bot = crud.create_bot(
            session=db, bot_in=_bot_in(account.id), owner_id=user.id
        )

        assert bot.status == BotStatusEnum.stopped
        crud.start_bot(session=db, bot=bot)
        assert bot.status == BotStatusEnum.pending
        crud.stop_bot(session=db, bot=bot)
        assert bot.status == BotStatusEnum.stopped
