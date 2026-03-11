from fastapi_users.db import SQLAlchemyBaseUserTable
from sqlalchemy import (
    Column,
    ForeignKey,
    Integer,
    String,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from src.app.models.db_models.base import BaseFields


class UserORM(SQLAlchemyBaseUserTable[int], BaseFields):
    __tablename__ = "user"
    name: Mapped[str] = mapped_column(nullable=True)
    phone_number: Mapped[str] = mapped_column(
        String(20), unique=True, nullable=True
    )
    revoked_tokens = relationship("RevokedToken", back_populates="user")
    orders = relationship("OrderORM", back_populates="user")
    payments = relationship("PaymentORM", back_populates="user")


class RevokedToken(BaseFields):
    __tablename__ = "revoked_tokens"

    token = Column(String, unique=True, nullable=False)
    user_id = Column(Integer, ForeignKey("user.id"), nullable=False)
    user = relationship("UserORM", back_populates="revoked_tokens")
