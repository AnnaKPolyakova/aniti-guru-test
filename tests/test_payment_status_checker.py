"""Tests for PaymentStatusChecker (check and update payment status via acquiring)."""

from datetime import UTC, datetime
from unittest.mock import AsyncMock

import pytest
from sqlalchemy.ext.asyncio import AsyncSession
from src.app.clients.acquiring import (
    AcquiringCheckError,
    AcquiringPaymentNotFoundError,
)
from src.app.models.db_models.order import OrderORM, OrderPaymentStatus
from src.app.models.db_models.payment import PaymentORM, PaymentStatus
from src.app.services.payment import PaymentStatusChecker


@pytest.mark.asyncio
async def test_status_checker_payment_not_found_returns_true(
    db_session: AsyncSession,
) -> None:
    """When no updatable payment exists (e.g. wrong id), check_and_update returns True."""
    mock_client = AsyncMock()
    checker = PaymentStatusChecker(db_session, acquiring_client=mock_client)
    result = await checker.check_and_update(payment_id=99999)
    assert result is True
    mock_client.check_payment.assert_not_called()


@pytest.mark.asyncio
async def test_status_checker_acquiring_not_found_returns_false(
    db_session: AsyncSession,
    submitted_payment: PaymentORM,
) -> None:
    """When bank returns payment not found, check_and_update returns False (retry later)."""
    payment = submitted_payment
    mock_client = AsyncMock()
    mock_client.check_payment.side_effect = AcquiringPaymentNotFoundError()
    checker = PaymentStatusChecker(db_session, acquiring_client=mock_client)
    result = await checker.check_and_update(payment_id=payment.id)
    assert result is False
    mock_client.check_payment.assert_called_once_with(
        bank_payment_id=payment.bank_payment_id
    )


@pytest.mark.asyncio
async def test_status_checker_acquiring_check_error_returns_false(
    db_session: AsyncSession,
    submitted_payment: PaymentORM,
) -> None:
    """When bank check raises temporary error, check_and_update returns False."""
    payment = submitted_payment
    mock_client = AsyncMock()
    mock_client.check_payment.side_effect = AcquiringCheckError()
    checker = PaymentStatusChecker(db_session, acquiring_client=mock_client)
    result = await checker.check_and_update(payment_id=payment.id)
    assert result is False


@pytest.mark.asyncio
async def test_status_checker_bank_returns_rejected_updates_db_returns_true(
    db_session: AsyncSession,
    submitted_payment: PaymentORM,
) -> None:
    """When bank returns Rejected, payment status is updated and True is returned."""
    payment = submitted_payment
    mock_client = AsyncMock()
    mock_client.check_payment.return_value = {
        "payment_id": payment.bank_payment_id,
        "amount": str(payment.amount),
        "status": PaymentStatus.Rejected.value,
        "paid_at": datetime.now(UTC).isoformat(),
    }
    checker = PaymentStatusChecker(db_session, acquiring_client=mock_client)
    result = await checker.check_and_update(payment_id=payment.id)
    assert result is True
    await db_session.refresh(payment)
    assert payment.payment_status == PaymentStatus.Rejected.value


@pytest.mark.asyncio
async def test_status_checker_bank_returns_completed_updates_payment_and_order(
    db_session: AsyncSession,
    order: OrderORM,
    submitted_payment: PaymentORM,
) -> None:
    """When bank returns Completed, payment and order status are updated."""
    payment = submitted_payment
    paid_at = datetime.now(UTC)
    mock_client = AsyncMock()
    mock_client.check_payment.return_value = {
        "payment_id": payment.bank_payment_id,
        "amount": str(payment.amount),
        "status": PaymentStatus.Completed.value,
        "paid_at": paid_at.isoformat(),
    }
    checker = PaymentStatusChecker(db_session, acquiring_client=mock_client)
    result = await checker.check_and_update(payment_id=payment.id)
    assert result is True
    await db_session.refresh(payment)
    await db_session.refresh(order)
    assert payment.payment_status == PaymentStatus.Completed.value
    assert payment.paid_at is not None
    assert order.payment_status == OrderPaymentStatus.PAID.value


@pytest.mark.asyncio
async def test_status_checker_bank_returns_processing_returns_false(
    db_session: AsyncSession,
    submitted_payment: PaymentORM,
) -> None:
    """When bank returns Processing, payment is updated but False (retry later)."""
    payment = submitted_payment
    mock_client = AsyncMock()
    mock_client.check_payment.return_value = {
        "payment_id": payment.bank_payment_id,
        "amount": str(payment.amount),
        "status": PaymentStatus.Processing.value,
        "paid_at": datetime.now(UTC).isoformat(),
    }
    checker = PaymentStatusChecker(db_session, acquiring_client=mock_client)
    result = await checker.check_and_update(payment_id=payment.id)
    assert result is False
    await db_session.refresh(payment)
    assert payment.payment_status == PaymentStatus.Processing.value


@pytest.mark.asyncio
async def test_status_checker_invalid_payment_info_raises(
    db_session: AsyncSession,
    submitted_payment: PaymentORM,
) -> None:
    """When bank returns invalid payload, ValueError is raised."""
    payment = submitted_payment
    mock_client = AsyncMock()
    mock_client.check_payment.return_value = {
        "payment_id": payment.bank_payment_id,
        "invalid_key": "invalid",
    }
    checker = PaymentStatusChecker(db_session, acquiring_client=mock_client)
    with pytest.raises(ValueError, match="Invalid payment info"):
        await checker.check_and_update(payment_id=payment.id)
