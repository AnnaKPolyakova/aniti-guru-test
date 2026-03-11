from fastapi_users import schemas
from pydantic import BaseModel, EmailStr


class UserCreateRequest(schemas.BaseUser[int]):
    pass


class UserCreateResponse(schemas.BaseUserCreate):
    pass


class UserDict(BaseModel):
    id: int
    email: EmailStr


class LoginRequest(BaseModel):
    email: EmailStr
    password: str


class LoginResponse(BaseModel):
    access_token: str
    refresh_token: str


class UserRead(schemas.BaseUser[int]):
    pass


class UserCreate(schemas.BaseUserCreate):
    pass


class UserUpdate(schemas.BaseUserUpdate):
    pass
