from typing import Any, cast

from fastapi import APIRouter, Depends, Request, Response
from fastapi_users import FastAPIUsers
from fastapi_users.authentication import Strategy
from starlette.responses import JSONResponse

from src.app.models.db_models import UserORM
from src.app.models.validators.user import (
    UserCreate,
    UserRead,
    UserUpdate,
)
from src.app.services.users import (
    auth_backend,
    get_user_manager,
    refresh_backend,
)
from src.app.tasks import check_payment_status_task

auth_router = APIRouter(
    prefix="/auth",
    tags=["auth"],
)

fastapi_users = FastAPIUsers(
    get_user_manager,
    [
        auth_backend,
    ],
)

fastapi_users_refresh = FastAPIUsers(
    get_user_manager,
    [refresh_backend],
)

# JWT login
auth_router.include_router(
    fastapi_users.get_auth_router(auth_backend),
    prefix="/jwt",
    tags=["users"],
)

# Registration
auth_router.include_router(
    fastapi_users.get_register_router(UserRead, UserCreate),
    prefix="/users",
    tags=["users"],
)

# Users
auth_router.include_router(
    fastapi_users.get_users_router(UserRead, UserUpdate),
    prefix="/users",
    tags=["users"],
)


@auth_router.post("/jwt/refresh")
async def refresh(
    user: UserORM = Depends(fastapi_users_refresh.current_user(active=True)),
) -> Response:
    strategy = cast(Strategy[Any, Any], auth_backend.get_strategy())
    access_token = await strategy.write_token(user)
    check_payment_status_task.apply_async(args=(2,))
    return JSONResponse(
        content={"access_token": access_token, "token_type": "bearer"},
        status_code=200,
    )


@auth_router.post(
    "/jwt/logout_refresh",
)
async def logout_refresh(
    request: Request,
    response: Response,
    user: UserORM = Depends(fastapi_users_refresh.current_user(active=True)),
) -> Response:
    # Get token from cookie
    refresh_token = request.cookies.get("refresh_token")
    strategy = cast(Strategy[Any, Any], auth_backend.get_strategy())
    return await auth_backend.logout(strategy, user, refresh_token)  # type: ignore[arg-type]
