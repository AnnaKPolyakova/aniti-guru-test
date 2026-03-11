"""Tests for ReturnPaymentService (create cash return payment)."""

from decimal import Decimal

import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.app.models.db_models.order import OrderORM, OrderPaymentStatus
from src.app.models.db_models.payment import (
    OperationType,
    PaymentORM,
    PaymentStatus,
    PaymentType,
)
from src.app.models.db_models.user import UserORM
from src.app.services.payment.exceptions import (
    ForbiddenOrderAccessError,
    OrderNotFoundError,
    ReturnAmountExceedsBalanceError,
)
from src.app.services.payment.return_service import ReturnPaymentService

from tests.factories import OrderFactory, PaymentFactory, UserFactory


@pytest.fixture
async def order_with_completed_payment(
    db_session: AsyncSession,
) -> tuple[OrderORM, PaymentORM, UserORM]:
    """Order with one completed deposit payment (paid in full)."""
    user = UserFactory.build()
    db_session.add(user)
    await db_session.flush()

    order = OrderFactory.build(user=user, total_sum=Decimal("500.00"))
    db_session.add(order)
    await db_session.flush()

    payment = PaymentFactory.build(
        user=user,
        order=order,
        amount=order.total_sum,
        payment_status=PaymentStatus.Completed.value,
        operation_type=OperationType.Deposit.value,
    )
    db_session.add(payment)
    await db_session.commit()
    await db_session.refresh(order)
    return order, payment, user


@pytest.mark.asyncio
async def test_create_return_success(
    db_session: AsyncSession,
    order_with_completed_payment: tuple[OrderORM, PaymentORM, UserORM],
) -> None:
    """Create return payment and recalculate order payment_status."""
    order, _deposit, user = order_with_completed_payment
    return_amount = Decimal("100.00")

    service = ReturnPaymentService(session=db_session, order_id=order.id)
    payment = await service.create_return(user=user, amount=return_amount)

    assert payment.operation_type == OperationType.Return.value
    assert payment.payment_type == PaymentType.CASH.value
    assert payment.payment_status == PaymentStatus.Completed.value
    assert payment.amount == return_amount
    assert payment.order_id == order.id
    assert payment.user_id == user.id
    assert payment.bank_payment_id is None
    assert payment.paid_at is not None

    await db_session.refresh(order)
    assert order.payment_status == OrderPaymentStatus.PARTIALLY_PAID.value


@pytest.mark.asyncio
async def test_create_return_full_amount_updates_order_to_unpaid(
    db_session: AsyncSession,
    order_with_completed_payment: tuple[OrderORM, PaymentORM, UserORM],
) -> None:
    """Return full paid amount sets order payment_status to UNPAID."""
    order, _deposit, user = order_with_completed_payment

    service = ReturnPaymentService(session=db_session, order_id=order.id)
    await service.create_return(user=user, amount=order.total_sum)

    await db_session.refresh(order)
    assert order.payment_status == OrderPaymentStatus.UNPAID.value


@pytest.mark.asyncio
async def test_create_return_exceeds_balance_raises(
    db_session: AsyncSession,
    order_with_completed_payment: tuple[OrderORM, PaymentORM, UserORM],
) -> None:
    """Return amount greater than completed balance raises error."""
    order, _deposit, user = order_with_completed_payment
    return_amount = order.total_sum + Decimal("1.00")

    service = ReturnPaymentService(session=db_session, order_id=order.id)

    with pytest.raises(ReturnAmountExceedsBalanceError) as exc_info:
        await service.create_return(user=user, amount=return_amount)

    assert exc_info.value.available_amount == order.total_sum

    result = await db_session.execute(
        select(PaymentORM).where(
            PaymentORM.order_id == order.id,
            PaymentORM.operation_type == OperationType.Return.value,
        )
    )
    assert result.scalar_one_or_none() is None


@pytest.mark.asyncio
async def test_create_return_foreign_order_forbidden(
    db_session: AsyncSession,
    order_with_completed_payment: tuple[OrderORM, PaymentORM, UserORM],
) -> None:
    """User cannot create return for another user's order."""
    order, _deposit, _owner = order_with_completed_payment
    other_user = UserFactory.build()
    db_session.add(other_user)
    await db_session.flush()

    service = ReturnPaymentService(session=db_session, order_id=order.id)

    with pytest.raises(ForbiddenOrderAccessError):
        await service.create_return(user=other_user, amount=Decimal("10.00"))


@pytest.mark.asyncio
async def test_create_return_order_not_found(
    db_session: AsyncSession,
    user: UserORM,
) -> None:
    """Non-existent order_id raises OrderNotFoundError."""
    service = ReturnPaymentService(session=db_session, order_id=99999)

    with pytest.raises(OrderNotFoundError):
        await service.create_return(user=user, amount=Decimal("10.00"))
