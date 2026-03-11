"""Service for checking and updating payment status via acquiring API."""

from decimal import ROUND_HALF_UP, Decimal
from typing import Any

from loguru import logger
from pydantic import ValidationError
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.clients.acquiring import (
    AcquiringCheckError,
    AcquiringClient,
    AcquiringPaymentNotFoundError,
)
from src.app.models.db_models.order import OrderORM, OrderPaymentStatus
from src.app.models.db_models.payment import (
    OperationType,
    PaymentORM,
    PaymentStatus,
)
from src.app.models.validators.payment import AcquiringPaymentInfo


class PaymentStatusChecker:
    """Check payment status via acquiring API and update the database."""

    def __init__(
        self,
        session: AsyncSession,
        acquiring_client: AcquiringClient | None = None,
    ) -> None:
        self.session = session
        self.acquiring_client = acquiring_client or AcquiringClient()

    async def _get_payment_for_update(
        self, payment_id: int
    ) -> PaymentORM | None:
        """Return payment for update by id with lock, or None."""
        result = await self.session.execute(
            select(PaymentORM)
            .where(
                PaymentORM.id == payment_id,
                ~PaymentORM.payment_status.in_(
                    [
                        PaymentStatus.Completed.value,
                        PaymentStatus.Rejected.value,
                    ]
                ),
                PaymentORM.bank_payment_id.isnot(None),
            )
            .with_for_update()
        )
        return result.scalar_one_or_none()

    @staticmethod
    async def _check_payment_info(
        payment_info: dict[str, Any],
    ) -> AcquiringPaymentInfo:
        """Validate payment data from acquiring."""
        try:
            return AcquiringPaymentInfo(**payment_info)
        except ValidationError as e:
            logger.error(
                "Invalid payment info from acquiring: {}",
                e,
                payment_info=payment_info,
            )
            raise ValueError("Invalid payment info") from e

    async def _get_order_payment_status(self, order: OrderORM) -> str:
        """Compute order payment status from completed payments."""
        sum_expr = func.coalesce(
            func.sum(
                case(
                    (
                        PaymentORM.operation_type
                        == OperationType.Deposit.value,
                        PaymentORM.amount,
                    ),
                    (
                        PaymentORM.operation_type
                        == OperationType.Return.value,
                        -PaymentORM.amount,
                    ),
                    else_=0,
                )
            ),
            0,
        )
        result = await self.session.execute(
            select(sum_expr).where(
                PaymentORM.order_id == order.id,
                PaymentORM.payment_status == PaymentStatus.Completed.value,
            )
        )
        total_sum = result.scalar_one() or 0
        if total_sum == Decimal(order.total_sum).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        ):
            return OrderPaymentStatus.PAID.value
        if total_sum == Decimal(0).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        ):
            return OrderPaymentStatus.UNPAID.value
        return OrderPaymentStatus.PARTIALLY_PAID.value

    async def check_and_update(self, payment_id: int) -> bool:
        """Check payment status in acquiring and update the database.

        Returns:
            True if payment is in terminal state (Completed/Rejected
            or not found); False if check should be retried later.
        """
        payment = await self._get_payment_for_update(payment_id)
        if payment is None:
            logger.debug(
                "Payment {} already terminal or not found, skipping check",
                payment_id,
            )
            return True
        try:
            payment_info: dict[
                str, Any
            ] = await self.acquiring_client.check_payment(
                bank_payment_id=payment.bank_payment_id
            )
        except AcquiringPaymentNotFoundError:
            logger.opt(exception=True).warning(
                "Payment not found in acquiring, will retry: payment_id={}, bank_payment_id={}",
                payment_id,
                payment.bank_payment_id,
            )
            return False
        except AcquiringCheckError:
            logger.opt(exception=True).warning(
                "Acquiring check failed, will retry: payment_id={}, bank_payment_id={}",
                payment_id,
                payment.bank_payment_id,
            )
            return False
        payment_info_valid = await self._check_payment_info(payment_info)
        new_status = payment_info_valid.status
        if new_status not in [
            s.value for s in PaymentStatus.__members__.values()
        ]:
            return False
        payment.payment_status = new_status
        if new_status == PaymentStatus.Completed.value:
            payment.paid_at = payment_info_valid.paid_at
            payment.order.payment_status = (
                await self._get_order_payment_status(payment.order)
            )
        await self.session.commit()
        logger.info(
            "Payment status updated: payment_id={}, new_status={}, order_id={}",
            payment_id,
            new_status,
            payment.order_id,
        )
        return new_status in [
            PaymentStatus.Completed.value,
            PaymentStatus.Rejected.value,
        ]
