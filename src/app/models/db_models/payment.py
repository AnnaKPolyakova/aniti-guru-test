from __future__ import annotations

import enum
from datetime import datetime
from decimal import Decimal
from typing import TYPE_CHECKING

from sqlalchemy import DateTime, ForeignKey, Integer, Numeric, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.app.models.db_models.base import BaseFields
from src.app.models.db_models.user import UserORM

if TYPE_CHECKING:
    from src.app.models.db_models.order import OrderORM


class PaymentType(str, enum.Enum):
    CASH = "cash"
    ACQUIRING = "acquiring"


class OperationType(str, enum.Enum):
    Deposit = "deposit"
    Return = "return"


class PaymentStatus(str, enum.Enum):
    Submitted = "submitted"  # submitted
    Processing = "processing"  # in progress
    Completed = "completed"  # completed
    Rejected = "rejected"  # rejected


class PaymentORM(BaseFields):
    __tablename__ = "payment"

    user_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("user.id"), nullable=False
    )
    user: Mapped[UserORM] = relationship("UserORM", back_populates="payments")
    payment_status: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=PaymentStatus.Submitted.value,
    )
    payment_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=PaymentType.ACQUIRING.value,
    )
    operation_type: Mapped[str] = mapped_column(
        String(20),
        nullable=False,
        default=OperationType.Deposit.value,
    )
    order_id: Mapped[int] = mapped_column(
        Integer, ForeignKey("order.id"), nullable=False
    )
    order: Mapped[OrderORM] = relationship(
        "OrderORM", back_populates="payments"
    )
    amount: Mapped[Decimal] = mapped_column(
        Numeric(10, 2, asdecimal=True), nullable=False
    )
    bank_payment_id: Mapped[str] = mapped_column(String(255), nullable=True)
    paid_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
