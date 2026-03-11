from __future__ import annotations

from decimal import Decimal

from bot_engine.workers import base


class DummyRedis:
    def __init__(self) -> None:
        self.data: dict[str, str] = {}

    def get(self, key: str):
        return self.data.get(key)

    def delete(self, key: str) -> None:
        self.data.pop(key, None)


class DummyTask(base.AsyncBotTask):
    name = "dummy-task"


class TestRedisStopSignal:
    def test_should_stop_true_and_false(self, monkeypatch) -> None:
        r = DummyRedis()
        bot_id = "bot-1"
        monkeypatch.setattr(base, "get_redis", lambda: r)

        assert base.should_stop(bot_id) is False
        r.data[f"bot:{bot_id}:stop"] = "1"
        assert base.should_stop(bot_id) is True

    def test_clear_stop_signal(self, monkeypatch) -> None:
        r = DummyRedis()
        bot_id = "bot-2"
        r.data[f"bot:{bot_id}:stop"] = "1"
        monkeypatch.setattr(base, "get_redis", lambda: r)

        base.clear_stop_signal(bot_id)
        assert base.should_stop(bot_id) is False


class TestRiskHelpers:
    def test_calc_change_pct(self) -> None:
        assert base.calc_change_pct(Decimal("110"), Decimal("100")) == Decimal("10")
        assert base.calc_change_pct(Decimal("90"), Decimal("100")) == Decimal("-10")
        assert base.calc_change_pct(Decimal("100"), Decimal("0")) == Decimal("0")

    def test_evaluate_risk_limits_stop_loss(self) -> None:
        result = base.evaluate_risk_limits(
            change_pct=Decimal("-5.2"),
            stop_loss_pct=Decimal("5"),
            take_profit_pct=Decimal("10"),
        )
        assert result is not None
        status, reason = result
        assert status == "stopped"
        assert "stop-loss" in reason.lower()

    def test_evaluate_risk_limits_take_profit(self) -> None:
        result = base.evaluate_risk_limits(
            change_pct=Decimal("12.3"),
            stop_loss_pct=Decimal("5"),
            take_profit_pct=Decimal("10"),
        )
        assert result is not None
        status, reason = result
        assert status == "completed"
        assert "take-profit" in reason.lower()

    def test_evaluate_risk_limits_none(self) -> None:
        result = base.evaluate_risk_limits(
            change_pct=Decimal("2.0"),
            stop_loss_pct=Decimal("5"),
            take_profit_pct=Decimal("10"),
        )
        assert result is None


class TestAsyncBotTask:
    def test_run_async_returns_result(self) -> None:
        task = DummyTask()

        async def _work():
            return "ok"

        assert task.run_async(_work()) == "ok"

    def test_on_failure_calls_helpers(self, monkeypatch) -> None:
        task = DummyTask()
        calls: dict[str, tuple] = {}

        def _log(**kwargs):
            calls["log"] = (kwargs["bot_id"], kwargs["event_type"], kwargs["level"])

        def _status(*, bot_id: str, error_message: str):
            calls["status"] = (bot_id, error_message)

        monkeypatch.setattr(base, "_create_bot_log", _log)
        monkeypatch.setattr(base, "_update_bot_status_error", _status)

        task.on_failure(
            RuntimeError("boom"),
            task_id="task-1",
            args=(),
            kwargs={"bot_id": "bot-3"},
            einfo=None,
        )

        assert calls["log"] == ("bot-3", "task_failure", "error")
        assert calls["status"] == ("bot-3", "boom")

    def test_on_success_logs_for_known_bot(self, monkeypatch) -> None:
        task = DummyTask()
        calls: dict[str, tuple] = {}

        def _log(**kwargs):
            calls["log"] = (kwargs["bot_id"], kwargs["event_type"], kwargs["level"])

        monkeypatch.setattr(base, "_create_bot_log", _log)

        task.on_success(
            retval=None,
            task_id="task-2",
            args=(),
            kwargs={"bot_id": "bot-4"},
        )

        assert calls["log"] == ("bot-4", "task_success", "info")
