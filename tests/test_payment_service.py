"""Tests for PaymentService (create acquiring deposit payment)."""

from decimal import ROUND_HALF_UP, Decimal
from http import HTTPStatus

import httpx
import pytest
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from src.app.models.db_models.order import OrderORM
from src.app.models.db_models.payment import PaymentORM, PaymentStatus
from src.app.models.db_models.user import UserORM

from tests.conftest import ERROR_INFO, PAYMENT_ID


@pytest.mark.asyncio
async def test_create_payment_success(
    async_client: httpx.AsyncClient,
    db_session: AsyncSession,
    user: UserORM,
    access_token: str,
    order: OrderORM,
) -> None:
    """Successful acquiring deposit payment and order status update."""
    url = "/payments/deposit/acquiring"
    method = "post"
    amount = float(
        Decimal(order.total_sum / 2).quantize(
            Decimal("0.01"), rounding=ROUND_HALF_UP
        )
    )
    payload = {
        "order_id": order.id,
        "amount": amount,
    }
    headers = {"Authorization": f"Bearer {access_token}"}

    response = await getattr(async_client, method)(
        url,
        json=payload,
        headers=headers,
    )
    data = response.json()

    assert response.status_code == HTTPStatus.CREATED, ERROR_INFO.format(
        method=method, url=url, status=HTTPStatus.CREATED
    )
    assert data["order_id"] == order.id
    assert data["amount"] == str(amount)
    assert data["payment_status"] == PaymentStatus.Submitted.value
    assert data["bank_payment_id"] == PAYMENT_ID


@pytest.mark.asyncio
async def test_create_payment_overpayment(
    async_client: httpx.AsyncClient,
    db_session: AsyncSession,
    user: UserORM,
    access_token: str,
    order: OrderORM,
) -> None:
    """Overpayment for acquiring deposit is rejected."""
    url = "/payments/deposit/acquiring"
    method = "post"
    amount = Decimal(order.total_sum * 2).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    payload = {
        "order_id": order.id,
        "amount": float(amount),
    }
    headers = {"Authorization": f"Bearer {access_token}"}

    response = await getattr(async_client, method)(
        url,
        json=payload,
        headers=headers,
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST, ERROR_INFO.format(
        method=method, url=url, status=HTTPStatus.BAD_REQUEST
    )
    stmt = select(PaymentORM).where(PaymentORM.order_id == order.id)
    payments = (await db_session.execute(stmt)).scalars().all()
    assert payments == []


@pytest.mark.asyncio
async def test_create_payment_full_payment(
    async_client: httpx.AsyncClient,
    db_session: AsyncSession,
    user: UserORM,
    access_token: str,
    order: OrderORM,
) -> None:
    """Full acquiring deposit payment closes order as PAID."""
    url = "/payments/deposit/acquiring"
    method = "post"
    amount = order.total_sum
    payload = {
        "order_id": order.id,
        "amount": float(amount),
    }
    headers = {"Authorization": f"Bearer {access_token}"}

    response = await getattr(async_client, method)(
        url,
        json=payload,
        headers=headers,
    )

    assert response.status_code == HTTPStatus.CREATED, ERROR_INFO.format(
        method=method, url=url, status=HTTPStatus.CREATED
    )


@pytest.mark.asyncio
async def test_create_payment_foreign_order_forbidden(  # noqa: PLR0913
    async_client: httpx.AsyncClient,
    db_session: AsyncSession,
    user: UserORM,
    access_token: str,
    access_token_for_user_2: str,
    order: OrderORM,
) -> None:
    """User cannot make acquiring deposit payment for someone else's order."""
    url = "/payments/deposit/acquiring"
    method = "post"
    amount = Decimal(order.total_sum / 2).quantize(
        Decimal("0.01"), rounding=ROUND_HALF_UP
    )
    payload = {
        "order_id": order.id,
        "amount": float(amount),
    }
    headers = {"Authorization": f"Bearer {access_token_for_user_2}"}

    response = await getattr(async_client, method)(
        url,
        json=payload,
        headers=headers,
    )

    assert response.status_code == HTTPStatus.FORBIDDEN, ERROR_INFO.format(
        method=method, url=url, status=HTTPStatus.FORBIDDEN
    )
