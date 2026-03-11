import asyncio
from collections.abc import AsyncGenerator, Generator
from decimal import Decimal

import httpx
import pytest
import redis
from asgi_lifespan import LifespanManager
from fastapi import FastAPI
from fastapi_users.db import SQLAlchemyUserDatabase
from httpx import ASGITransport
from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession, create_async_engine
from src.app.clients.acquiring import AcquiringClient
from src.app.core.config import settings
from src.app.db.postgres import get_postgres_provider
from src.app.main import create_app
from src.app.models.db_models import (
    Base,
    OrderORM,
    UserORM,
)
from src.app.models.db_models.payment import PaymentORM, PaymentStatus
from src.app.services.users import (
    JWTStrategyWithBlacklist,
    UserManager,
    get_jwt_strategy,
    get_refresh_strategy,
)

from tests.factories import (
    OrderFactory,
    PaymentFactory,
    UserFactory,
)

ERROR_INFO = "Error for method: {method}, url: {url}, status: {status}"
PAYMENT_ID = "bank-payment-id-1"


@pytest.fixture(scope="session", autouse=True)
async def postgres_db() -> AsyncGenerator[None]:
    """Create test DB, create tables, drop DB after tests."""
    # test database name
    admin_engine = create_async_engine(
        settings.POSTGRES_URL, isolation_level="AUTOCOMMIT"
    )
    # 1. Connect to postgres (admin)
    async with admin_engine.connect() as conn:
        # Check if database exists
        result = await conn.execute(
            text(
                "SELECT 1 FROM pg_database WHERE datname = :db_name"
            ).bindparams(db_name=settings.POSTGRES_TEST_DB)
        )
        exists = result.scalar() is not None
        if exists:
            await conn.execute(
                text(f"DROP DATABASE {settings.POSTGRES_TEST_DB}")
            )
        await conn.execute(
            text(f"CREATE DATABASE {settings.POSTGRES_TEST_DB}")
        )
        print(f"Test DB created: {settings.POSTGRES_TEST_DB}")

    # Engine for test database
    test_db_url = settings.POSTGRES_TEST_URL
    async_engine = create_async_engine(test_db_url, future=True)

    # Create tables
    async with async_engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    yield

    # Drop database
    # 1. Close engine and pool
    await async_engine.dispose()

    async with admin_engine.connect() as conn:
        # 2. Terminate all connections
        await conn.execute(
            text(
                "SELECT pg_terminate_backend(pid) "
                "FROM pg_stat_activity "
                "WHERE datname = :db_name AND pid <> pg_backend_pid();"
            ).bindparams(db_name=settings.POSTGRES_TEST_DB)
        )

        # 3. Drop database
        await conn.execute(text(f"DROP DATABASE {settings.POSTGRES_TEST_DB}"))


@pytest.fixture(scope="session", autouse=True)
def redis_db() -> Generator[redis.Redis]:
    pool = redis.ConnectionPool(
        host=settings.REDIS_HOST,
        port=settings.REDIS_PORT,
        db=settings.REDIS_TEST_DB,
        password=settings.REDIS_PASSWORD,
    )
    client = redis.Redis(connection_pool=pool)
    client.flushdb()

    yield client

    # Clean up after all tests complete
    client.flushdb()


@pytest.fixture(scope="session", autouse=True)
async def test_app() -> FastAPI:
    settings.TEST = True
    app_instance = create_app(settings.TEST)
    return app_instance


@pytest.fixture(autouse=True)
async def async_client(test_app: FastAPI) -> AsyncGenerator[httpx.AsyncClient]:
    # LifespanManager ensures startup/shutdown are called
    async with LifespanManager(test_app):
        transport = ASGITransport(app=test_app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            yield client


@pytest.fixture(autouse=True)
async def db_session() -> AsyncGenerator[AsyncSession]:
    """Fixture to get DB session."""
    pg_provider = get_postgres_provider(test=True)
    await pg_provider.connect()
    if pg_provider.async_session_maker is None:
        raise RuntimeError("Async session maker is not available")
    async with pg_provider.async_session_maker() as session:
        yield session


@pytest.fixture(autouse=True)
def event_loop() -> Generator[asyncio.AbstractEventLoop]:
    """Create a single event loop for the whole pytest session."""
    loop = asyncio.get_event_loop_policy().new_event_loop()
    yield loop
    loop.close()


@pytest.fixture
async def user_manager(
    db_session: AsyncSession,
) -> UserManager[UserORM]:
    """Fixture to get UserManager."""
    user_db: SQLAlchemyUserDatabase[UserORM, int] = SQLAlchemyUserDatabase(
        db_session, UserORM
    )
    manager: UserManager[UserORM] = UserManager(user_db)
    return manager


@pytest.fixture
async def user(
    user_manager: UserManager[UserORM],
    db_session: AsyncSession,
) -> UserORM:
    """Fixture to create a test user."""
    user: UserORM = UserFactory.build()
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def user_2(
    user_manager: UserManager[UserORM],
    db_session: AsyncSession,
) -> UserORM:
    """Fixture to create a second test user."""
    user: UserORM = UserFactory.build()
    db_session.add(user)
    await db_session.commit()
    await db_session.refresh(user)
    return user


@pytest.fixture
async def access_token(
    user_manager: UserManager[UserORM],
    db_session: AsyncSession,
    user: UserORM,
) -> str:
    """Fixture to create access token for the test user."""
    strategy: JWTStrategyWithBlacklist[UserORM, int] = get_jwt_strategy()
    return await strategy.write_token(user)


@pytest.fixture
async def access_token_for_user_2(
    user_manager: UserManager[UserORM],
    db_session: AsyncSession,
    user_2: UserORM,
) -> str:
    """Fixture to create access token for the second test user."""
    strategy: JWTStrategyWithBlacklist[UserORM, int] = get_jwt_strategy()
    return await strategy.write_token(user_2)


@pytest.fixture
async def refresh_token(
    user_manager: UserManager[UserORM],
    db_session: AsyncSession,
    user: UserORM,
) -> str:
    """Fixture to create refresh token for the test user."""
    strategy: JWTStrategyWithBlacklist[UserORM, int] = get_refresh_strategy()
    return await strategy.write_token(user)


@pytest.fixture
async def order(db_session: AsyncSession, user: UserORM) -> OrderORM:
    """Fixture to create an order."""
    order_obj: OrderORM = OrderFactory.build(user=user)
    db_session.add(order_obj)
    await db_session.commit()
    return order_obj


@pytest.fixture
async def submitted_payment(
    db_session: AsyncSession,
    user: UserORM,
    order: OrderORM,
) -> PaymentORM:
    """Payment in Submitted status for PaymentStatusChecker tests."""
    payment: PaymentORM = PaymentFactory.build(
        user=user,
        order=order,
        amount=order.total_sum,
        payment_status=PaymentStatus.Submitted.value,
        bank_payment_id="bank-pay-1",
    )
    db_session.add(payment)
    await db_session.commit()
    return payment


@pytest.fixture(autouse=True)
async def mock_bank_start(monkeypatch: pytest.MonkeyPatch) -> None:
    async def _ok(
        self: AcquiringClient, order_id: int, amount: Decimal
    ) -> str:
        return PAYMENT_ID

    monkeypatch.setattr(AcquiringClient, "start_payment", _ok)
