from datetime import datetime

from pydantic import BaseModel, Field


class CatalogItemRead(BaseModel):
    """Schema for reading catalog item"""

    id: int
    name: str = Field(..., max_length=255)
    description: str | None = Field(None, max_length=1000)
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class CatalogItemCreate(BaseModel):
    """Schema for creating catalog item"""

    name: str = Field(..., max_length=255)
    description: str | None = Field(None, max_length=1000)


class CatalogItemUpdate(BaseModel):
    """Schema for updating catalog item"""

    name: str | None = Field(None, max_length=255)
    description: str | None = Field(None, max_length=1000)


class CatalogItemListResponse(BaseModel):
    """Schema for paginated catalog items list"""

    items: list[CatalogItemRead]
    total: int
    page: int
    page_size: int
    prev_page: str | None = None
    next_page: str | None = None
