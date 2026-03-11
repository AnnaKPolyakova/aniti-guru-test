from collections.abc import AsyncGenerator
from contextlib import asynccontextmanager

from loguru import logger
from sqlalchemy.ext.asyncio import AsyncSession

from src.app.core.config import settings
from src.app.db.postgres import PgConnector


@asynccontextmanager
async def postgres_session() -> AsyncGenerator[AsyncSession]:
    """
    Context manager: creates engine, connects and yields a session.
    On exit from the block, session and engine are closed automatically.
    """
    postgres_provider = PgConnector(url=settings.POSTGRES_URL)
    try:
        await postgres_provider.connect()
        if postgres_provider.async_session_maker is None:
            logger.error(
                "Async session maker is not available in postgres_session"
            )
            raise RuntimeError("Async session maker is not available")
        async with postgres_provider.async_session_maker() as session:
            yield session
    finally:
        await postgres_provider.close()
