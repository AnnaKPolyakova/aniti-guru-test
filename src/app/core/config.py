import os
from pathlib import Path

from dotenv import load_dotenv
from pydantic_settings import BaseSettings

load_dotenv()


BASE_DIR = Path(__file__).resolve().parent.parent.parent


class Settings(BaseSettings):
    PROJECT_NAME: str = "name"
    APP_ENV: str = "dev"
    APP_PORT: int = 8000
    APP_HOST: str = "127.0.0.1"
    APP_LOG_LEVEL: str = "INFO"
    REDIS_HOST: str = "127.0.0.1"
    REDIS_PORT: int = 6376
    REDIS_PROTOCOL: str = "redis"
    REDIS_PASSWORD: str = "redis"
    REDIS_DB: str = "0"
    REDIS_TEST_DB: str = "15"
    PAGE_SIZE: int = 10

    POSTGRES_PASSWORD: str = "password"
    POSTGRES_HOST: str = "localhost"
    POSTGRES_PORT: int = 5432
    POSTGRES_DB: str = "database"
    POSTGRES_USER: str = "user"

    SECRET_KEY: str = "supersecretkey"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 30
    REFRESH_TOKEN_EXPIRE_DAYS: int = 7
    TEST: bool = False

    ACQUIRING_START_URL: str = "https://test/START"
    ACQUIRING_CHECK_URL: str = "https://test/CHECK"

    @property
    def CELERY_BROKER_URL(self) -> str:
        return self.REDIS_URL

    @property
    def CELERY_RESULT_BACKEND(self) -> str:
        return self.REDIS_URL

    @property
    def AUTOFLUSH(self) -> bool:
        return True

    @property
    def AUTOFLUSH_TEST(self) -> bool:
        return False

    @property
    def POSTGRES_URL(self) -> str:
        return (
            "postgresql+asyncpg://{user}:{password}@{host}:{port}/{db}"
        ).format(
            user=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD,
            host=self.POSTGRES_HOST,
            port=self.POSTGRES_PORT,
            db=self.POSTGRES_DB,
        )

    @property
    def REDIS_URL(self) -> str:
        return "{protocol}://:{password}@{host}:{port}/{bd}".format(
            protocol=self.REDIS_PROTOCOL,
            host=self.REDIS_HOST,
            port=self.REDIS_PORT,
            password=self.REDIS_PASSWORD,
            bd=self.REDIS_DB,
        )

    @property
    def POSTGRES_TEST_DB(self) -> str:
        return self.POSTGRES_DB + "_test"

    @property
    def POSTGRES_TEST_URL(self) -> str:
        return (
            "postgresql+asyncpg://{user}:{password}@{host}:{port}/{db}"
        ).format(
            user=self.POSTGRES_USER,
            password=self.POSTGRES_PASSWORD,
            host=self.POSTGRES_HOST,
            port=self.POSTGRES_PORT,
            db=self.POSTGRES_TEST_DB,
        )

    @property
    def REDIS_TEST_URL(self) -> str:
        return "{protocol}://:{password}@{host}:{port}/{db}".format(
            protocol=self.REDIS_PROTOCOL,
            host=self.REDIS_HOST,
            port=self.REDIS_PORT,
            db=self.REDIS_TEST_DB,
            password=self.REDIS_PASSWORD,
        )

    class Config:
        env_file = os.path.join(BASE_DIR, ".env")
        env_file_encoding = "utf-8"


settings = Settings()
