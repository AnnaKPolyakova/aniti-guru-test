from pydantic import BaseModel, Field

from src.app.models.db_models.order import OrderPaymentStatus


class OrderPaymentUpdate(BaseModel):
    """Schema for updating payment status"""

    payment_status: OrderPaymentStatus = Field(
        ..., description="New payment status for order"
    )
