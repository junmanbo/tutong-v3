"""migrate_bot_currency_usdt_to_krw

Revision ID: c9d8e7f6a5b4
Revises: b4c5d6e7f8a9
Create Date: 2026-03-08 00:40:00.000000

"""
from alembic import op


# revision identifiers, used by Alembic.
revision = "c9d8e7f6a5b4"
down_revision = "b4c5d6e7f8a9"
branch_labels = None
depends_on = None


def upgrade():
    # 1) symbol: BTC/USDT -> BTC/KRW
    op.execute(
        """
        UPDATE bot
        SET symbol = regexp_replace(symbol, '/USDT$', '/KRW', 'i')
        WHERE symbol ~* '/USDT$'
        """
    )

    # 2) quote_currency: USDT -> KRW
    op.execute(
        """
        UPDATE bot
        SET quote_currency = 'KRW'
        WHERE upper(quote_currency) = 'USDT'
        """
    )

    # 3) config.quote: USDT -> KRW
    op.execute(
        """
        UPDATE bot
        SET config = jsonb_set(config, '{quote}', to_jsonb('KRW'::text), true)
        WHERE upper(coalesce(config->>'quote', '')) = 'USDT'
        """
    )

    # 4) config.assets: {"USDT": x} -> {"KRW": x}
    op.execute(
        """
        UPDATE bot
        SET config = jsonb_set(
            config,
            '{assets}',
            ((config->'assets') - 'USDT') || jsonb_build_object('KRW', config->'assets'->'USDT'),
            true
        )
        WHERE jsonb_typeof(config->'assets') = 'object'
          AND (config->'assets' ? 'USDT')
        """
    )


def downgrade():
    # downgrade은 대칭 변환으로 제공 (KRW -> USDT)
    op.execute(
        """
        UPDATE bot
        SET symbol = regexp_replace(symbol, '/KRW$', '/USDT', 'i')
        WHERE symbol ~* '/KRW$'
        """
    )

    op.execute(
        """
        UPDATE bot
        SET quote_currency = 'USDT'
        WHERE upper(quote_currency) = 'KRW'
        """
    )

    op.execute(
        """
        UPDATE bot
        SET config = jsonb_set(config, '{quote}', to_jsonb('USDT'::text), true)
        WHERE upper(coalesce(config->>'quote', '')) = 'KRW'
        """
    )

    op.execute(
        """
        UPDATE bot
        SET config = jsonb_set(
            config,
            '{assets}',
            ((config->'assets') - 'KRW') || jsonb_build_object('USDT', config->'assets'->'KRW'),
            true
        )
        WHERE jsonb_typeof(config->'assets') = 'object'
          AND (config->'assets' ? 'KRW')
        """
    )
