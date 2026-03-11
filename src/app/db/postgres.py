from collections.abc import AsyncGenerator

from fastapi import Depends
from loguru import logger
from sqlalchemy.ext.asyncio import (
    AsyncEngine,
    AsyncSession,
    async_sessionmaker,
    create_async_engine,
)

from src.app.core.config import settings


class PgConnector:
    def __init__(self, url: str, autoflush: bool = True):
        self._url = url
        self._engine: AsyncEngine | None = None
        self._async_session_maker: async_sessionmaker[AsyncSession] | None = (
            None
        )
        self._autoflush = autoflush

    async def get_session(self) -> AsyncGenerator[AsyncSession]:
        if self._async_session_maker is None:
            return
        async with self._async_session_maker() as session:
            yield session

    async def connect(self) -> None:
        try:
            self._engine = create_async_engine(
                self._url,
                pool_pre_ping=True,
                future=True,
            )
            self._async_session_maker = async_sessionmaker(
                bind=self._engine,
                class_=AsyncSession,
                expire_on_commit=False,
                autoflush=self._autoflush,
            )
            logger.info("Postgres initialized")
        except Exception as e:
            logger.exception("Postgres init failed: %s", e)

    async def close(self) -> None:
        if self._engine is not None:
            try:
                await self._engine.dispose()
            except Exception:
                logger.exception("Error during Postgres shutdown")

    @property
    def async_session_maker(
        self,
    ) -> async_sessionmaker[AsyncSession] | None:
        if self._async_session_maker is None:
            logger.error(
                "Async session maker is not available (Postgres not connected)"
            )
            raise RuntimeError("Async session maker is not available")
        return self._async_session_maker


postgres_provider: PgConnector | None = None


def get_postgres_provider(test: bool = settings.TEST) -> PgConnector:
    global postgres_provider  # noqa: PLW0603
    if postgres_provider is None:
        if test:
            postgres_provider = PgConnector(url=settings.POSTGRES_TEST_URL)
        else:
            postgres_provider = PgConnector(url=settings.POSTGRES_URL)
    return postgres_provider


async def get_async_db_session(
    pg_provider: PgConnector = Depends(get_postgres_provider),
) -> AsyncGenerator[AsyncSession]:
    if pg_provider.async_session_maker is None:
        logger.error(
            "Async session maker is not available when getting DB session"
        )
        raise RuntimeError("Async session maker is not available")
    async with pg_provider.async_session_maker() as session:
        try:
            yield session
        except Exception as e:
            logger.exception(
                "DB session error, rolling back: %s",
                e,
            )
            await session.rollback()
            raise
        finally:
            await session.close()
