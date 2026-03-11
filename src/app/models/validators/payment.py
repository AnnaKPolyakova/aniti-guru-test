from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, Field

from src.app.models.db_models.payment import (
    OperationType,
    PaymentStatus,
    PaymentType,
)


class PaymentCreate(BaseModel):
    """Schema for creating acquiring deposit payment for order."""

    order_id: int = Field(..., description="ID of the order to pay for")
    amount: Decimal = Field(
        max_digits=10, decimal_places=2, gt=0, description="Payment amount"
    )


class PaymentRead(BaseModel):
    """Schema for reading payment info."""

    id: int
    order_id: int
    user_id: int
    amount: Decimal = Field(max_digits=10, decimal_places=2)
    payment_status: PaymentStatus
    payment_type: PaymentType
    operation_type: OperationType
    bank_payment_id: str | None = None
    paid_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class AcquiringPaymentInfo(BaseModel):
    payment_id: str
    amount: Decimal
    status: str
    paid_at: datetime
