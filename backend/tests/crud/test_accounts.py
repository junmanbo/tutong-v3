"""ExchangeAccount CRUD 함수 단위 테스트.

DB 레이어를 직접 테스트합니다.
커버리지 목표: 80%+
"""
import json
import uuid

from sqlmodel import Session

from app import crud
from app.core.config import settings
from app.core.crypto import decrypt
from app.models import (
    ExchangeAccountCreate,
    ExchangeAccountUpdate,
    ExchangeTypeEnum,
)
from tests.utils.user import create_random_user
from tests.utils.utils import random_lower_string


# ── 헬퍼 ──────────────────────────────────────────────────────────────────────


def _account_in(**overrides) -> ExchangeAccountCreate:
    data: dict = dict(
        exchange=ExchangeTypeEnum.binance,
        label=random_lower_string()[:20],
        api_key=random_lower_string(),
        api_secret=random_lower_string(),
    )
    data.update(overrides)
    return ExchangeAccountCreate(**data)


# ── create_exchange_account ────────────────────────────────────────────────────


class TestCreateExchangeAccount:
    def test_create_account_returns_model(self, db: Session) -> None:
        user = create_random_user(db)
        account = crud.create_exchange_account(
            session=db, account_in=_account_in(), owner_id=user.id
        )
        assert account.id is not None
        assert account.user_id == user.id

    def test_exchange_and_label_stored_correctly(self, db: Session) -> None:
        user = create_random_user(db)
        label = random_lower_string()[:20]
        account = crud.create_exchange_account(
            session=db,
            account_in=_account_in(
                exchange=ExchangeTypeEnum.upbit, label=label
            ),
            owner_id=user.id,
        )
        assert account.exchange == ExchangeTypeEnum.upbit
        assert account.label == label

    def test_api_keys_are_encrypted(self, db: Session) -> None:
        """평문 API 키가 암호화되어 저장되어야 함."""
        user = create_random_user(db)
        plain_key = "my-plain-api-key"
        plain_secret = "my-plain-secret"
        account = crud.create_exchange_account(
            session=db,
            account_in=_account_in(api_key=plain_key, api_secret=plain_secret),
            owner_id=user.id,
        )
        # 암호화된 값이 평문과 달라야 함
        assert account.api_key_enc != plain_key
        assert account.api_secret_enc != plain_secret
        assert len(account.api_key_enc) > 0
        assert len(account.api_secret_enc) > 0

    def test_api_keys_decrypt_back_to_original_plaintext(self, db: Session) -> None:
        """암호화 저장된 키는 올바른 ENCRYPTION_KEY로 복호화 가능해야 한다."""
        user = create_random_user(db)
        plain_key = "my-plain-api-key"
        plain_secret = "my-plain-secret"
        account = crud.create_exchange_account(
            session=db,
            account_in=_account_in(api_key=plain_key, api_secret=plain_secret),
            owner_id=user.id,
        )

        assert decrypt(account.api_key_enc, settings.ENCRYPTION_KEY) == plain_key
        assert decrypt(account.api_secret_enc, settings.ENCRYPTION_KEY) == plain_secret

    def test_same_plaintext_produces_different_ciphertext(self, db: Session) -> None:
        """AES-GCM nonce 랜덤성으로 동일 평문도 다른 암호문이 저장되어야 한다."""
        user = create_random_user(db)
        account1 = crud.create_exchange_account(
            session=db,
            account_in=_account_in(
                api_key="same-key",
                api_secret="same-secret",
            ),
            owner_id=user.id,
        )
        account2 = crud.create_exchange_account(
            session=db,
            account_in=_account_in(
                api_key="same-key",
                api_secret="same-secret",
            ),
            owner_id=user.id,
        )

        assert account1.api_key_enc != account2.api_key_enc
        assert account1.api_secret_enc != account2.api_secret_enc

    def test_extra_params_encrypted_when_provided(self, db: Session) -> None:
        user = create_random_user(db)
        extra = {"account_number": "987654321"}
        account = crud.create_exchange_account(
            session=db,
            account_in=_account_in(extra_params=extra),
            owner_id=user.id,
        )
        assert account.extra_params_enc is not None
        # 암호화된 값에 평문이 노출되지 않아야 함
        assert "987654321" not in account.extra_params_enc

    def test_extra_params_decrypt_round_trip(self, db: Session) -> None:
        user = create_random_user(db)
        extra = {"account_number": "987654321", "CANO": "12345678"}
        account = crud.create_exchange_account(
            session=db,
            account_in=_account_in(extra_params=extra),
            owner_id=user.id,
        )

        assert account.extra_params_enc is not None
        decrypted = decrypt(account.extra_params_enc, settings.ENCRYPTION_KEY)
        assert json.loads(decrypted) == extra

    def test_extra_params_none_when_not_provided(self, db: Session) -> None:
        user = create_random_user(db)
        account = crud.create_exchange_account(
            session=db,
            account_in=_account_in(extra_params=None),
            owner_id=user.id,
        )
        assert account.extra_params_enc is None

    def test_default_is_active_true(self, db: Session) -> None:
        user = create_random_user(db)
        account = crud.create_exchange_account(
            session=db, account_in=_account_in(), owner_id=user.id
        )
        assert account.is_active is True

    def test_default_is_valid_false(self, db: Session) -> None:
        """신규 계좌는 자격증명 미검증 상태."""
        user = create_random_user(db)
        account = crud.create_exchange_account(
            session=db, account_in=_account_in(), owner_id=user.id
        )
        assert account.is_valid is False

    def test_default_deleted_at_none(self, db: Session) -> None:
        user = create_random_user(db)
        account = crud.create_exchange_account(
            session=db, account_in=_account_in(), owner_id=user.id
        )
        assert account.deleted_at is None

    def test_timestamps_set_on_create(self, db: Session) -> None:
        user = create_random_user(db)
        account = crud.create_exchange_account(
            session=db, account_in=_account_in(), owner_id=user.id
        )
        assert account.created_at is not None
        assert account.updated_at is not None


# ── get_exchange_account ───────────────────────────────────────────────────────


class TestGetExchangeAccount:
    def test_get_account_returns_correct_record(self, db: Session) -> None:
        user = create_random_user(db)
        account = crud.create_exchange_account(
            session=db, account_in=_account_in(), owner_id=user.id
        )

        fetched = crud.get_exchange_account(
            session=db, account_id=account.id, user_id=user.id
        )
        assert fetched is not None
        assert fetched.id == account.id

    def test_get_account_wrong_user_returns_none(self, db: Session) -> None:
        """다른 사용자의 계좌는 조회 불가."""
        user1 = create_random_user(db)
        user2 = create_random_user(db)
        account = crud.create_exchange_account(
            session=db, account_in=_account_in(), owner_id=user1.id
        )

        fetched = crud.get_exchange_account(
            session=db, account_id=account.id, user_id=user2.id
        )
        assert fetched is None

    def test_get_nonexistent_account_returns_none(self, db: Session) -> None:
        user = create_random_user(db)
        fetched = crud.get_exchange_account(
            session=db, account_id=uuid.uuid4(), user_id=user.id
        )
        assert fetched is None

    def test_get_soft_deleted_account_returns_none(
        self, db: Session
    ) -> None:
        user = create_random_user(db)
        account = crud.create_exchange_account(
            session=db, account_in=_account_in(), owner_id=user.id
        )
        crud.delete_exchange_account(session=db, account=account)

        fetched = crud.get_exchange_account(
            session=db, account_id=account.id, user_id=user.id
        )
        assert fetched is None


# ── get_exchange_accounts_by_user ─────────────────────────────────────────────


class TestGetExchangeAccountsByUser:
    def test_returns_user_accounts(self, db: Session) -> None:
        user = create_random_user(db)
        crud.create_exchange_account(
            session=db, account_in=_account_in(), owner_id=user.id
        )
        crud.create_exchange_account(
            session=db, account_in=_account_in(), owner_id=user.id
        )

        accounts = crud.get_exchange_accounts_by_user(
            session=db, user_id=user.id
        )
        assert len(accounts) == 2

    def test_excludes_other_users_accounts(self, db: Session) -> None:
        user1 = create_random_user(db)
        user2 = create_random_user(db)
        crud.create_exchange_account(
            session=db, account_in=_account_in(), owner_id=user1.id
        )

        accounts = crud.get_exchange_accounts_by_user(
            session=db, user_id=user2.id
        )
        assert len(accounts) == 0

    def test_excludes_soft_deleted_accounts(self, db: Session) -> None:
        user = create_random_user(db)
        account = crud.create_exchange_account(
            session=db, account_in=_account_in(), owner_id=user.id
        )
        crud.delete_exchange_account(session=db, account=account)

        accounts = crud.get_exchange_accounts_by_user(
            session=db, user_id=user.id
        )
        assert len(accounts) == 0

    def test_pagination_skip(self, db: Session) -> None:
        user = create_random_user(db)
        for _ in range(3):
            crud.create_exchange_account(
                session=db, account_in=_account_in(), owner_id=user.id
            )

        accounts = crud.get_exchange_accounts_by_user(
            session=db, user_id=user.id, skip=2
        )
        assert len(accounts) == 1

    def test_pagination_limit(self, db: Session) -> None:
        user = create_random_user(db)
        for _ in range(3):
            crud.create_exchange_account(
                session=db, account_in=_account_in(), owner_id=user.id
            )

        accounts = crud.get_exchange_accounts_by_user(
            session=db, user_id=user.id, limit=2
        )
        assert len(accounts) == 2

    def test_empty_list_for_new_user(self, db: Session) -> None:
        user = create_random_user(db)
        accounts = crud.get_exchange_accounts_by_user(
            session=db, user_id=user.id
        )
        assert accounts == []


# ── count_active_accounts ─────────────────────────────────────────────────────


class TestCountActiveAccounts:
    def test_count_active_accounts(self, db: Session) -> None:
        user = create_random_user(db)
        crud.create_exchange_account(
            session=db, account_in=_account_in(), owner_id=user.id
        )
        crud.create_exchange_account(
            session=db, account_in=_account_in(), owner_id=user.id
        )

        count = crud.count_active_accounts(session=db, user_id=user.id)
        assert count == 2

    def test_count_excludes_deleted(self, db: Session) -> None:
        user = create_random_user(db)
        account = crud.create_exchange_account(
            session=db, account_in=_account_in(), owner_id=user.id
        )
        crud.delete_exchange_account(session=db, account=account)

        count = crud.count_active_accounts(session=db, user_id=user.id)
        assert count == 0

    def test_count_zero_for_new_user(self, db: Session) -> None:
        user = create_random_user(db)
        count = crud.count_active_accounts(session=db, user_id=user.id)
        assert count == 0


# ── update_exchange_account ───────────────────────────────────────────────────


class TestUpdateExchangeAccount:
    def test_update_label(self, db: Session) -> None:
        user = create_random_user(db)
        account = crud.create_exchange_account(
            session=db,
            account_in=_account_in(label="Old Label"),
            owner_id=user.id,
        )

        updated = crud.update_exchange_account(
            session=db,
            account=account,
            account_in=ExchangeAccountUpdate(label="New Label"),
        )
        assert updated.label == "New Label"

    def test_update_is_active(self, db: Session) -> None:
        user = create_random_user(db)
        account = crud.create_exchange_account(
            session=db, account_in=_account_in(), owner_id=user.id
        )
        assert account.is_active is True

        updated = crud.update_exchange_account(
            session=db,
            account=account,
            account_in=ExchangeAccountUpdate(is_active=False),
        )
        assert updated.is_active is False

    def test_update_sets_updated_at(self, db: Session) -> None:
        user = create_random_user(db)
        account = crud.create_exchange_account(
            session=db, account_in=_account_in(), owner_id=user.id
        )
        original_updated_at = account.updated_at

        updated = crud.update_exchange_account(
            session=db,
            account=account,
            account_in=ExchangeAccountUpdate(label="New Label"),
        )
        assert updated.updated_at >= original_updated_at

    def test_partial_update_leaves_other_fields_unchanged(
        self, db: Session
    ) -> None:
        user = create_random_user(db)
        account = crud.create_exchange_account(
            session=db,
            account_in=_account_in(
                exchange=ExchangeTypeEnum.upbit, label="Upbit Acct"
            ),
            owner_id=user.id,
        )
        original_key_enc = account.api_key_enc

        crud.update_exchange_account(
            session=db,
            account=account,
            account_in=ExchangeAccountUpdate(label="Updated Label"),
        )

        # 암호화된 키는 변경되지 않아야 함
        assert account.api_key_enc == original_key_enc
        assert account.exchange == ExchangeTypeEnum.upbit


# ── delete_exchange_account ───────────────────────────────────────────────────


class TestDeleteExchangeAccount:
    def test_delete_sets_deleted_at(self, db: Session) -> None:
        user = create_random_user(db)
        account = crud.create_exchange_account(
            session=db, account_in=_account_in(), owner_id=user.id
        )
        assert account.deleted_at is None

        crud.delete_exchange_account(session=db, account=account)
        assert account.deleted_at is not None

    def test_deleted_account_not_in_list(self, db: Session) -> None:
        user = create_random_user(db)
        account = crud.create_exchange_account(
            session=db, account_in=_account_in(), owner_id=user.id
        )
        crud.delete_exchange_account(session=db, account=account)

        accounts = crud.get_exchange_accounts_by_user(
            session=db, user_id=user.id
        )
        assert account.id not in [a.id for a in accounts]

    def test_deleted_account_not_fetchable_by_id(self, db: Session) -> None:
        user = create_random_user(db)
        account = crud.create_exchange_account(
            session=db, account_in=_account_in(), owner_id=user.id
        )
        crud.delete_exchange_account(session=db, account=account)

        fetched = crud.get_exchange_account(
            session=db, account_id=account.id, user_id=user.id
        )
        assert fetched is None
