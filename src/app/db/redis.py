from loguru import logger
from collections.abc import AsyncGenerator

from redis.asyncio import Redis, from_url

from src.app.core.config import settings

class RedisClient:
    def __init__(self, url: str):
        self.url = url
        self._redis: Redis | None = None

    async def connect(self) -> None:
        self._redis = from_url(self.url)
        logger.info("Redis initialized")

    async def disconnect(self) -> None:
        if self._redis is not None:
            await self._redis.close()
            logger.info("Redis closed")

    async def get_redis(self) -> Redis | None:
        return self._redis


redis_provider: RedisClient | None = None


def get_redis_provider(test: bool = False) -> RedisClient:
    global redis_provider  # noqa: PLW0603
    if test:
        redis_provider = RedisClient(settings.REDIS_TEST_URL)
    else:
        redis_provider = RedisClient(settings.REDIS_URL)
    return redis_provider


async def get_redis() -> AsyncGenerator[RedisClient | None]:
    yield redis_provider

