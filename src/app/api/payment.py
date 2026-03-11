"""Payment endpoints: acquiring deposit and returns."""

from fastapi import APIRouter, Depends, HTTPException, status
from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.api.auth import fastapi_users
from src.app.clients.acquiring import AcquiringStartError
from src.app.db.postgres import get_async_db_session
from src.app.models.db_models.payment import (
    PaymentORM,
    PaymentType,
)
from src.app.models.db_models.user import UserORM
from src.app.models.validators.payment import PaymentCreate, PaymentRead
from src.app.services.payment import (
    ForbiddenOrderAccessError,
    OrderNotFoundError,
    OverpaymentError,
    PaymentService,
    ReturnAmountExceedsBalanceError,
    ReturnPaymentService,
)

deposit_acquiring_router = APIRouter(
    prefix="/payments",
    tags=["payments"],
)


@deposit_acquiring_router.post(
    "/deposit/acquiring",
    response_model=PaymentRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_acquiring_deposit_payment(
    payload: PaymentCreate,
    session: AsyncSession = Depends(get_async_db_session),
    user: UserORM = Depends(fastapi_users.current_user(active=True)),
) -> PaymentORM:
    """Create an acquiring deposit payment for an order."""
    service = PaymentService(session=session, order_id=payload.order_id)
    try:
        payment = await service.create_acquiring_payment(
            user=user,
            amount=payload.amount,
            payment_type=PaymentType.ACQUIRING.value,
        )
    except OrderNotFoundError as e:
        logger.warning(
            "Order not found for acquiring deposit: order_id={}, user_id={}",
            payload.order_id,
            user.id,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found",
        ) from e
    except OverpaymentError as e:
        logger.warning(
            "Overpayment for order: order_id={}, user_id={}, remaining={}",
            payload.order_id,
            user.id,
            e.remaining_amount,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Payment amount exceeds remaining order amount. "
                f"Remaining amount: {e.remaining_amount}"
            ),
        ) from e
    except ForbiddenOrderAccessError as e:
        logger.warning(
            "Forbidden order access for acquiring: order_id={}, user_id={}",
            payload.order_id,
            user.id,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot pay for this order",
        ) from e
    except AcquiringStartError as e:
        logger.opt(exception=True).error(
            "Acquiring start failed: order_id={}, user_id={}",
            payload.order_id,
            user.id,
        )
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Please try again later",
        ) from e

    logger.info(
        "Acquiring deposit created via API: payment_id={}, order_id={}, user_id={}",
        payment.id,
        payload.order_id,
        user.id,
    )
    return payment


@deposit_acquiring_router.post(
    "/return",
    response_model=PaymentRead,
    status_code=status.HTTP_201_CREATED,
)
async def create_return_payment(
    payload: PaymentCreate,
    session: AsyncSession = Depends(get_async_db_session),
    user: UserORM = Depends(fastapi_users.current_user(active=True)),
) -> PaymentORM:
    """Create a return payment for an order."""
    service = ReturnPaymentService(session=session, order_id=payload.order_id)
    try:
        payment = await service.create_return(
            user=user,
            amount=payload.amount,
        )
    except OrderNotFoundError as e:
        logger.warning(
            "Order not found for return: order_id={}, user_id={}",
            payload.order_id,
            user.id,
        )
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Order not found",
        ) from e
    except ReturnAmountExceedsBalanceError as e:
        logger.warning(
            "Return amount exceeds balance: order_id={}, user_id={}, available={}",
            payload.order_id,
            user.id,
            e.available_amount,
        )
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=(
                "Return amount exceeds available balance. "
                f"Available amount: {e.available_amount}"
            ),
        ) from e
    except ForbiddenOrderAccessError as e:
        logger.warning(
            "Forbidden order access for return: order_id={}, user_id={}",
            payload.order_id,
            user.id,
        )
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="You cannot create return for this order",
        ) from e

    logger.info(
        "Return payment created via API: payment_id={}, order_id={}, user_id={}",
        payment.id,
        payload.order_id,
        user.id,
    )
    return payment
