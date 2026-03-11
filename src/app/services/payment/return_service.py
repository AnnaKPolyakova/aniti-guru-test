"""Service for creating cash returns for an order."""

from datetime import UTC, datetime
from decimal import Decimal

from loguru import logger
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.models.db_models.order import OrderORM
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
from src.app.services.payment.status_checker import PaymentStatusChecker


class ReturnPaymentService:
    """Create cash return for an order and recalculate order payment status."""

    def __init__(self, session: AsyncSession, order_id: int) -> None:
        self.session = session
        self.order_id = order_id

    async def _get_order_for_update(self) -> OrderORM:
        """Get order by id with lock; raise OrderNotFoundError if missing."""
        result = await self.session.execute(
            select(OrderORM)
            .where(OrderORM.id == self.order_id)
            .with_for_update()
        )
        order = result.scalar_one_or_none()
        if order is None:
            logger.warning(
                "Order not found: order_id={}",
                self.order_id,
            )
            raise OrderNotFoundError
        return order

    @staticmethod
    def _check_order_belongs_to_user(
        order: OrderORM,
        user: UserORM,
    ) -> None:
        """Ensure order belongs to user; otherwise raise ForbiddenOrderAccessError."""
        if order.user_id != user.id:
            logger.warning(
                "Order access forbidden for return: order_id={}, user_id={}",
                order.id,
                user.id,
            )
            raise ForbiddenOrderAccessError

    async def _get_completed_balance(self) -> Decimal:
        """Sum of completed payments for the order (deposits minus returns)."""
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
                PaymentORM.order_id == self.order_id,
                PaymentORM.payment_status == PaymentStatus.Completed.value,
            )
        )
        return Decimal(result.scalar_one() or 0)

    async def create_return(
        self,
        user: UserORM,
        amount: Decimal,
    ) -> PaymentORM:
        """Create cash return and recalculate order payment_status."""
        order = await self._get_order_for_update()
        self._check_order_belongs_to_user(order=order, user=user)

        completed_balance = await self._get_completed_balance()
        if amount > completed_balance:
            logger.warning(
                "Return amount exceeds balance: order_id={}, user_id={}, amount={}, available={}",
                self.order_id,
                user.id,
                amount,
                completed_balance,
            )
            raise ReturnAmountExceedsBalanceError(
                available_amount=completed_balance
            )

        payment = PaymentORM(
            user_id=user.id,
            order_id=self.order_id,
            amount=amount,
            payment_type=PaymentType.CASH.value,
            operation_type=OperationType.Return.value,
            payment_status=PaymentStatus.Completed.value,
            bank_payment_id=None,
            paid_at=datetime.now(UTC),
        )
        self.session.add(payment)
        await self.session.flush()

        status_checker = PaymentStatusChecker(self.session)
        order.payment_status = await status_checker._get_order_payment_status(
            order
        )

        await self.session.commit()
        logger.info(
            "Return payment created: payment_id={}, order_id={}, user_id={}, amount={}",
            payment.id,
            self.order_id,
            user.id,
            amount,
        )
        return payment
