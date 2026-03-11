import asyncio
from collections.abc import AsyncIterator, Callable
from contextlib import AbstractAsyncContextManager, asynccontextmanager
from typing import Any
from unittest.mock import AsyncMock, MagicMock

import pytest
from src.app.services.payment import PaymentStatusChecker
from src.app.tasks import (
    check_payment_status_task,
    enqueue_payment_status_checks_task,
)


class RetryCalled(Exception):
    """Custom exception to detect Celery retry in tests."""


def _run_sync_task_in_own_loop(task_run_fn: Callable[[], Any]) -> Any:
    """Run a sync Celery task that uses _run_async (run_until_complete) in its own loop."""
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    try:
        return task_run_fn()
    finally:
        loop.close()


def test_check_payment_status_task_final_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If payment is already in terminal status, retry is not called."""

    async def _ok(self: PaymentStatusChecker, payment_id: int) -> bool:
        return True

    monkeypatch.setattr(
        PaymentStatusChecker, "check_and_update", _ok, raising=True
    )

    def _retry(*args, **kwargs) -> None:  # type: ignore[no-untyped-def]
        raise RetryCalled

    monkeypatch.setattr(
        check_payment_status_task.__class__, "retry", _retry, raising=True
    )

    session = AsyncMock()
    mock_session_maker = MagicMock()
    mock_session_maker.return_value.__aenter__ = AsyncMock(
        return_value=session
    )
    mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=None)
    monkeypatch.setattr(
        "src.app.db.postgres.postgres_provider",
        MagicMock(async_session_maker=mock_session_maker),
    )

    _run_sync_task_in_own_loop(lambda: check_payment_status_task.run(1))


def test_check_payment_status_task_not_final_retries(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """If payment is not in terminal status yet, task retries."""

    async def _not_final(self: PaymentStatusChecker, payment_id: int) -> bool:
        return False

    monkeypatch.setattr(
        PaymentStatusChecker, "check_and_update", _not_final, raising=True
    )

    called = {"called": False}

    def _retry(self, *args, **kwargs) -> None:  # type: ignore[no-untyped-def]
        called["called"] = True
        raise RetryCalled

    monkeypatch.setattr(
        check_payment_status_task.__class__, "retry", _retry, raising=True
    )

    session = AsyncMock()
    mock_session_maker = MagicMock()
    mock_session_maker.return_value.__aenter__ = AsyncMock(
        return_value=session
    )
    mock_session_maker.return_value.__aexit__ = AsyncMock(return_value=None)
    monkeypatch.setattr(
        "src.app.db.postgres.postgres_provider",
        MagicMock(async_session_maker=mock_session_maker),
    )

    with pytest.raises(RetryCalled):
        _run_sync_task_in_own_loop(lambda: check_payment_status_task.run(1))

    assert called["called"] is True


# --- enqueue_payment_status_checks_task ---


def _fake_postgres_session(
    payment_ids: list[int],
) -> Callable[[], AbstractAsyncContextManager[AsyncMock]]:
    """Build async context manager that yields a session returning given ids from execute().all()."""

    class FakeResult:
        def all(self) -> list[tuple[int]]:
            return [(i,) for i in payment_ids]

    @asynccontextmanager
    async def _cm() -> AsyncIterator[AsyncMock]:
        session = AsyncMock()
        session.execute = AsyncMock(return_value=FakeResult())
        yield session

    return _cm


def test_enqueue_payment_status_checks_task_no_payments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """When there are no non-final payments, apply_async is never called."""
    monkeypatch.setattr(
        "src.app.tasks.tasks.postgres_session",
        _fake_postgres_session([]),
        raising=True,
    )
    apply_async_calls: list[tuple[int, bool]] = []
    monkeypatch.setattr(
        check_payment_status_task,
        "apply_async",
        lambda *args, **kwargs: apply_async_calls.append((args, kwargs)),
        raising=True,
    )

    _run_sync_task_in_own_loop(
        lambda: enqueue_payment_status_checks_task.run()
    )

    assert len(apply_async_calls) == 0


def test_enqueue_payment_status_checks_task_enqueues_for_each_payment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """For each non-final payment id, check_payment_status_task.apply_async is called."""
    apply_async_calls: list[tuple[tuple[Any, ...], dict[str, Any]]] = []
    payment_ids = [10, 20, 30]
    monkeypatch.setattr(
        "src.app.tasks.tasks.postgres_session",
        _fake_postgres_session(payment_ids),
        raising=True,
    )
    monkeypatch.setattr(
        check_payment_status_task,
        "apply_async",
        lambda *args, **kwargs: apply_async_calls.append((args, kwargs)),
        raising=True,
    )

    _run_sync_task_in_own_loop(
        lambda: enqueue_payment_status_checks_task.run()
    )

    assert len(apply_async_calls) == len(payment_ids)
    payment_ids_called = [c[1]["args"][0] for c in apply_async_calls]
    assert sorted(payment_ids_called) == payment_ids
