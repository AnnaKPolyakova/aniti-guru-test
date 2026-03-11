from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.responses import JSONResponse

from src.app.api.auth import auth_router
from src.app.api.payment import deposit_acquiring_router
from src.app.core.config import settings
from src.app.core.logger import setup_logging
from src.app.db.postgres import get_postgres_provider
from src.app.db.redis import get_redis_provider

routers = [
    auth_router,
    deposit_acquiring_router,
]


def create_app(test: bool) -> FastAPI:
    setup_logging()
    postgres_pr = get_postgres_provider(test=test)
    redis_pr = get_redis_provider(test=test)

    @asynccontextmanager
    async def lifespan(app: FastAPI) -> AsyncIterator[None]:
        # ---------- STARTUP ----------
        # Postgres init
        await postgres_pr.connect()

        # Redis init
        await redis_pr.connect()
        yield

        # ---------- SHUTDOWN ----------
        await postgres_pr.close()
        await redis_pr.disconnect()

    app: FastAPI = FastAPI(
        title=settings.PROJECT_NAME,
        docs_url="/docs",
        redoc_url="/redoc",
        openapi_url="/openapi.json",
        default_response_class=JSONResponse,
        lifespan=lifespan,
    )
    # # ---------- Middleware ----------
    # app.add_middleware(
    #     AuthMiddleware
    # )  # Must be first to set user in request.state
    # app.add_middleware(LoggingMiddleware)
    # app.add_middleware(MetricsMiddleware)

    # ---------- State ----------
    app.state.testing = test  # test mode flag

    for router in routers:
        app.include_router(router)

    return app
