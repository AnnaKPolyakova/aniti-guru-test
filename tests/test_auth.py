from http import HTTPStatus

import httpx
import pytest
from src.app.models.db_models import UserORM

from tests.conftest import ERROR_INFO
from tests.factories import PASSWORD


@pytest.mark.asyncio
async def test_register_user(
    async_client: httpx.AsyncClient,
) -> None:
    """New User Registration Test."""
    url = "/auth/users/register"
    method = "post"
    payload = {
        "email": "test@example.com",
        "password": PASSWORD,
    }
    response = await getattr(async_client, method)(url, json=payload)
    data = response.json()

    assert response.status_code == HTTPStatus.CREATED, ERROR_INFO.format(
        method=method, url=url, status=HTTPStatus.CREATED
    )
    assert "id" in data
    assert data["email"] == payload["email"]
    assert "hashed_password" not in data
    assert "password" not in data


@pytest.mark.asyncio
async def test_register_user_duplicate_email(
    async_client: httpx.AsyncClient,
) -> None:
    """Test registration with existing email."""
    url = "/auth/users/register"
    method = "post"
    payload = {
        "email": "duplicate@example.com",
        "password": PASSWORD,
    }

    # First registration
    response1 = await getattr(async_client, method)(url, json=payload)
    assert response1.status_code == HTTPStatus.CREATED

    # Second registration with the same email
    response2 = await getattr(async_client, method)(url, json=payload)
    assert response2.status_code == HTTPStatus.BAD_REQUEST, ERROR_INFO.format(
        method=method, url=url, status=HTTPStatus.BAD_REQUEST
    )


@pytest.mark.asyncio
async def test_register_user_invalid_email(
    async_client: httpx.AsyncClient,
) -> None:
    """Test registration with invalid email."""
    url = "/auth/users/register"
    method = "post"
    payload = {
        "email": "invalid-email",
        "password": "testpassword123",
    }
    response = await getattr(async_client, method)(url, json=payload)

    # fmt: off
    assert response.status_code == HTTPStatus.UNPROCESSABLE_ENTITY, (
        ERROR_INFO.format(
            method=method,
            url=url,
            status=HTTPStatus.UNPROCESSABLE_ENTITY,
        )
    )
    # fmt: on


@pytest.mark.asyncio
async def test_login_success(
    async_client: httpx.AsyncClient, user: UserORM
) -> None:
    """Test successful user login."""
    url = "/auth/jwt/login"
    method = "post"
    login_payload = {
        "username": user.email,
        "password": PASSWORD,
    }
    response = await getattr(async_client, method)(url, data=login_payload)
    data = response.json()

    assert response.status_code == HTTPStatus.OK, ERROR_INFO.format(
        method=method, url=url, status=HTTPStatus.OK
    )
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    # Check presence of refresh_token in cookies
    assert "refresh_token" in response.cookies


@pytest.mark.asyncio
async def test_login_invalid_credentials(
    async_client: httpx.AsyncClient, user: UserORM
) -> None:
    """Test login with invalid credentials."""
    login_url = "/auth/jwt/login"
    method = "post"
    login_payload = {
        "username": user.email,
        "password": "wrongpassword",
    }
    response = await getattr(async_client, method)(
        login_url, data=login_payload
    )

    assert response.status_code == HTTPStatus.BAD_REQUEST, ERROR_INFO.format(
        method=method, url=login_url, status=HTTPStatus.UNAUTHORIZED
    )


@pytest.mark.asyncio
async def test_get_current_user(
    async_client: httpx.AsyncClient, user: UserORM, access_token: str
) -> None:
    """Test getting current user information."""
    url = "/auth/users/me"
    method = "get"
    headers = {"Authorization": f"Bearer {access_token}"}
    response = await getattr(async_client, method)(url, headers=headers)
    data = response.json()

    assert response.status_code == HTTPStatus.OK, ERROR_INFO.format(
        method=method, url=url, status=HTTPStatus.OK
    )
    assert data["email"] == user.email
    assert "id" in data
    assert "hashed_password" not in data
    assert "password" not in data


@pytest.mark.asyncio
async def test_get_current_user_unauthorized(
    async_client: httpx.AsyncClient,
) -> None:
    """Test getting user information without authorization."""
    url = "/auth/users/me"
    method = "get"
    response = await getattr(async_client, method)(url)

    assert response.status_code == HTTPStatus.UNAUTHORIZED, ERROR_INFO.format(
        method=method, url=url, status=HTTPStatus.UNAUTHORIZED
    )


@pytest.mark.asyncio
async def test_get_current_user_invalid_token(
    async_client: httpx.AsyncClient,
) -> None:
    """Test to getting user information with invalid token."""
    me_url = "/auth/users/me"
    method = "get"
    headers = {"Authorization": "Bearer invalid_token_12345"}
    response = await getattr(async_client, method)(me_url, headers=headers)

    assert response.status_code == HTTPStatus.UNAUTHORIZED, ERROR_INFO.format(
        method=method, url=me_url, status=HTTPStatus.UNAUTHORIZED
    )


@pytest.mark.asyncio
async def test_update_current_user(
    async_client: httpx.AsyncClient, user: UserORM, access_token: str
) -> None:
    """Test updating current user information."""

    url = "/auth/users/me"
    method = "patch"
    headers = {"Authorization": f"Bearer {access_token}"}
    update_payload = {"email": "new-email@mail.ru"}
    response = await getattr(async_client, method)(
        url, headers=headers, json=update_payload
    )
    data = response.json()

    assert response.status_code == HTTPStatus.OK, ERROR_INFO.format(
        method=method, url=url, status=HTTPStatus.OK
    )
    assert data["email"] == "new-email@mail.ru"


@pytest.mark.asyncio
async def test_refresh_token(
    async_client: httpx.AsyncClient, user: UserORM, refresh_token: str
) -> None:
    """Test refreshing access token using refresh token."""

    url = "/auth/jwt/refresh"
    method = "post"
    cookies = {"refresh_token": refresh_token} if refresh_token else {}
    response = await getattr(async_client, method)(url, cookies=cookies)
    data = response.json()

    assert response.status_code == HTTPStatus.OK, ERROR_INFO.format(
        method=method, url=url, status=HTTPStatus.OK
    )
    assert "access_token" in data
    assert data["token_type"] == "bearer"


@pytest.mark.asyncio
async def test_refresh_token_unauthorized(
    async_client: httpx.AsyncClient,
) -> None:
    """Test refreshing token without refresh token."""
    url = "/auth/jwt/refresh"
    method = "post"
    response = await getattr(async_client, method)(url)

    assert response.status_code == HTTPStatus.UNAUTHORIZED, ERROR_INFO.format(
        method=method,
        url=url,
        status=HTTPStatus.UNAUTHORIZED,
    )


@pytest.mark.asyncio
async def test_logout(
    async_client: httpx.AsyncClient, user: UserORM, access_token: str
) -> None:
    """Test user logout."""
    url = "/auth/jwt/logout"
    method = "post"
    headers = {"Authorization": f"Bearer {access_token}"}
    response = await getattr(async_client, method)(url, headers=headers)

    assert response.status_code == HTTPStatus.OK, ERROR_INFO.format(
        method=method, url=url, status=HTTPStatus.OK
    )

    # Check that token no longer works
    me_url = "/auth/users/me"
    response = await async_client.get(me_url, headers=headers)
    assert response.status_code == HTTPStatus.UNAUTHORIZED


@pytest.mark.asyncio
async def test_logout_refresh(
    async_client: httpx.AsyncClient, user: UserORM, refresh_token: str
) -> None:
    """Test logout using refresh token."""

    logout_refresh_url = "/auth/jwt/logout_refresh"
    method = "post"
    cookies = {"refresh_token": refresh_token} if refresh_token else {}
    response = await getattr(async_client, method)(
        logout_refresh_url, cookies=cookies
    )

    assert response.status_code == HTTPStatus.OK, ERROR_INFO.format(
        method=method, url=logout_refresh_url, status=HTTPStatus.OK
    )

    # Check that refresh token no longer works
    refresh_url = "/auth/jwt/refresh"
    response = await async_client.post(refresh_url, cookies=cookies)
    assert response.status_code == HTTPStatus.UNAUTHORIZED


@pytest.mark.asyncio
async def test_logout_refresh_unauthorized(
    async_client: httpx.AsyncClient, access_token: str
) -> None:
    """Test logout via refresh token without token."""
    logout_refresh_url = "/auth/jwt/logout_refresh"
    method = "post"
    response = await getattr(async_client, method)(logout_refresh_url)

    assert response.status_code == HTTPStatus.UNAUTHORIZED, ERROR_INFO.format(
        method=method,
        url=logout_refresh_url,
        status=HTTPStatus.UNAUTHORIZED,
    )
