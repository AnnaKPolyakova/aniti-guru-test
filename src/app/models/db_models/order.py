from __future__ import annotations

import enum
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.app.models.db_models.base import BaseFields
from src.app.models.db_models.user import UserORM

if TYPE_CHECKING:
    from src.app.models.db_models.payment import PaymentORM


class OrderPaymentStatus(str, enum.Enum):
    """Payment status for orders."""

    UNPAID = "unpaid"
    PAID = "paid"
    PARTIALLY_PAID = "partially paid"


class OrderORM(BaseFields):
    __tablename__ = "order"

    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("user.id"), nullable=False
    )
    user: Mapped[UserORM] = relationship("UserORM", back_populates="orders")
    payment_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=OrderPaymentStatus.UNPAID.value,
    )
    total_sum: Mapped[Decimal] = mapped_column(
        Numeric(10, 2, asdecimal=True), nullable=False
    )
    payments: Mapped[list[PaymentORM]] = relationship(
        "PaymentORM", back_populates="order"
    )
