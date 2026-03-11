"""Service for creating acquiring deposit payments."""

from decimal import Decimal

from loguru import logger
from sqlalchemy import case, func, select
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.clients.acquiring import AcquiringClient
from src.app.models.db_models.order import OrderORM
from src.app.models.db_models.payment import (
    OperationType,
    PaymentORM,
    PaymentStatus,
)
from src.app.models.db_models.user import UserORM
from src.app.services.payment.exceptions import (
    ForbiddenOrderAccessError,
    OrderNotFoundError,
    OverpaymentError,
)
from src.app.tasks import check_payment_status_task


class PaymentService:
    """Create an acquiring deposit payment for an order."""

    def __init__(
        self,
        session: AsyncSession,
        order_id: int,
        acquiring_client: AcquiringClient | None = None,
    ) -> None:
        self.session = session
        self.order_id = order_id
        self.acquiring_client = acquiring_client or AcquiringClient()

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
                "Order access forbidden: order_id={}, user_id={}",
                order.id,
                user.id,
            )
            raise ForbiddenOrderAccessError

    async def _get_current_order_balance(self) -> Decimal:
        """Current order balance (successful and non-rejected payments)."""
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
                PaymentORM.payment_status != PaymentStatus.Rejected.value,
            )
        )
        return Decimal(result.scalar_one() or 0)

    @staticmethod
    def _check_amount(
        new_total_paid_with_in_process: Decimal,
        order: OrderORM,
        current_order_balance: Decimal,
    ) -> None:
        """Ensure amount does not exceed order total; otherwise raise OverpaymentError."""
        if new_total_paid_with_in_process > order.total_sum:
            remaining = order.total_sum - current_order_balance
            logger.warning(
                "Overpayment attempted: order_id={}, order_total={}, current_balance={}, remaining={}",
                order.id,
                order.total_sum,
                current_order_balance,
                remaining,
            )
            raise OverpaymentError(remaining_amount=remaining)

    async def create_acquiring_payment(
        self,
        user: UserORM,
        amount: Decimal,
        payment_type: str,
    ) -> PaymentORM:
        """Create acquiring deposit payment and enqueue status check task."""
        order = await self._get_order_for_update()
        self._check_order_belongs_to_user(order=order, user=user)
        current_balance_with_in_process = (
            await self._get_current_order_balance()
        )
        new_total_paid_with_in_process = (
            current_balance_with_in_process + amount
        )
        self._check_amount(
            new_total_paid_with_in_process=new_total_paid_with_in_process,
            order=order,
            current_order_balance=current_balance_with_in_process,
        )
        bank_payment_id = await self.acquiring_client.start_payment(
            order_id=order.id,
            amount=amount,
        )
        payment = PaymentORM(
            user_id=user.id,
            order_id=self.order_id,
            amount=amount,
            payment_type=payment_type,
            operation_type=OperationType.Deposit.value,
            payment_status=PaymentStatus.Submitted.value,
            bank_payment_id=bank_payment_id,
        )
        self.session.add(payment)
        await self.session.commit()
        check_payment_status_task.apply_async(args=(payment.id,))
        logger.info(
            "Acquiring payment created: payment_id={}, order_id={}, user_id={}, amount={}, bank_payment_id={}",
            payment.id,
            self.order_id,
            user.id,
            amount,
            bank_payment_id,
        )
        return payment
