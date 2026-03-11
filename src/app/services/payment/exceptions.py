from dataclasses import dataclass
from decimal import Decimal


@dataclass
class OverpaymentError(Exception):
    """Payment amount exceeds the remaining order amount."""

    remaining_amount: Decimal


class OrderNotFoundError(Exception):
    """Order not found."""


class ForbiddenOrderAccessError(Exception):
    """Access to the order is forbidden."""


class PaymentNotFoundError(Exception):
    """Payment not found."""


class ForbiddenPaymentAccessError(Exception):
    """Access to the payment is forbidden."""


class PaymentNotCancellableError(Exception):
    """Payment cannot be cancelled."""


@dataclass
class ReturnAmountExceedsBalanceError(Exception):
    """Return amount exceeds the available balance for the order."""

    available_amount: Decimal
