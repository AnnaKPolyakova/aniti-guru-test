from datetime import datetime

from pydantic import BaseModel, Field


class ProductRead(BaseModel):
    """Schema for reading product"""

    id: int
    catalog_item_id: int
    sell_price: float = Field(..., ge=0)
    purchase_price: float = Field(..., ge=0)
    quantity: int = Field(..., ge=0)
    created_at: datetime
    updated_at: datetime

    class Config:
        from_attributes = True


class ProductCreate(BaseModel):
    """Schema for creating product"""

    catalog_item_id: int = Field(..., description="ID of catalog item")
    sell_price: float = Field(..., ge=0, description="Selling price")
    purchase_price: float = Field(..., ge=0, description="Purchase price")
    quantity: int = Field(0, ge=0, description="Product quantity")


class ProductUpdate(BaseModel):
    """Schema for updating product"""

    catalog_item_id: int | None = Field(None, description="ID of catalog item")
    sell_price: float | None = Field(None, ge=0, description="Selling price")
    purchase_price: float | None = Field(
        None, ge=0, description="Purchase price"
    )
    quantity: int | None = Field(None, ge=0, description="Product quantity")


class ProductListResponse(BaseModel):
    """Schema for paginated products list"""

    items: list[ProductRead]
    total: int
    page: int
    page_size: int
    prev_page: str | None = None
    next_page: str | None = None
