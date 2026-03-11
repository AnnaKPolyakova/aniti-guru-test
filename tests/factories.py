from factory.alchemy import SQLAlchemyModelFactory
from factory.declarations import LazyFunction
from faker import Faker
from fastapi_users.password import PasswordHelper
from src.app.models.db_models import OrderORM, UserORM
from src.app.models.db_models.order import OrderPaymentStatus
from src.app.models.db_models.payment import (
    OperationType,
    PaymentORM,
    PaymentStatus,
    PaymentType,
)

PASSWORD = "password"
hashed_password = PasswordHelper().hash(PASSWORD)

fake = Faker()


def get_password_hash(password: str) -> str:
    return PasswordHelper().hash(password)


class UserFactory(SQLAlchemyModelFactory):
    class Meta:
        model = UserORM
        sqlalchemy_session_persistence = "flush"

    email = LazyFunction(lambda: fake.email())  # type: ignore
    hashed_password = LazyFunction(lambda: get_password_hash(PASSWORD))  # type: ignore


class OrderFactory(SQLAlchemyModelFactory):
    class Meta:
        model = OrderORM
        sqlalchemy_session_persistence = "flush"

    user = None
    total_sum = LazyFunction(
        lambda: round(fake.pyfloat(min_value=100, max_value=1000), 2)
    )  # type: ignore
    payment_status = OrderPaymentStatus.UNPAID.value


class PaymentFactory(SQLAlchemyModelFactory):
    class Meta:
        model = PaymentORM
        sqlalchemy_session_persistence = "flush"

    user = None
    order = None
    amount = LazyFunction(
        lambda: round(fake.pyfloat(min_value=10, max_value=100), 2)
    )  # type: ignore
    payment_status = PaymentStatus.Completed.value
    payment_type = PaymentType.ACQUIRING.value
    operation_type = OperationType.Deposit.value
    bank_payment_id = LazyFunction(lambda: f"bank-pay-{fake.uuid4()}")  # type: ignore
    paid_at = None  # Set when payment_status is Completed
