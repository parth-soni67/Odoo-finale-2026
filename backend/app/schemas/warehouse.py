from typing import Optional
from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class WarehouseBase(BaseModel):
    name: str = Field(..., min_length=1)
    location: str = Field(..., min_length=1)
    is_active: bool = True


class WarehouseCreate(WarehouseBase):
    pass


class WarehouseUpdate(BaseModel):
    name: Optional[str] = None
    location: Optional[str] = None
    is_active: Optional[bool] = None


class WarehouseResponse(WarehouseBase):
    id: int
    available_stock: Optional[int] = 0
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class InventoryStockCreate(BaseModel):
    warehouse_id: int
    product_id: int
    quantity: int = Field(..., gt=0, description="Quantity must be greater than 0")
    reason: Optional[str] = "Initial Stock"


class InventoryRestockCreate(BaseModel):
    quantity: int = Field(..., gt=0, description="Quantity must be greater than 0")
    reason: Optional[str] = "Restock"


class InventoryResponse(BaseModel):
    id: int
    warehouse_id: int
    warehouse_name: Optional[str] = None
    warehouse_location: Optional[str] = None
    product_id: int
    product_name: Optional[str] = None
    product_sku: Optional[str] = None
    category_name: Optional[str] = None
    fulfillment_type: Optional[str] = "PHYSICAL"
    quantity_on_hand: int = 0
    quantity_available: int = 0
    quantity_allocated: int = 0
    stock_status: Optional[str] = "IN STOCK"
    updated_at: Optional[datetime] = None

    model_config = ConfigDict(from_attributes=True)


class WarehouseCategoryProductSummary(BaseModel):
    product_id: int
    product_name: str
    sku: Optional[str] = None
    fulfillment_type: Optional[str] = "PHYSICAL"
    quantity_available: int = 0
    quantity_reserved: int = 0
    status: str = "IN STOCK"


class WarehouseCategorySummary(BaseModel):
    category_id: Optional[int] = None
    category_name: str
    total_units: int = 0
    products: list[WarehouseCategoryProductSummary] = []


class WarehouseInventorySummaryResponse(BaseModel):
    warehouse_id: int
    warehouse_name: str
    location: Optional[str] = None
    status: str = "ACTIVE"
    total_units: int = 0
    total_products: int = 0
    total_categories: int = 0
    low_stock_items: int = 0
    categories: list[WarehouseCategorySummary] = []


class WarehouseProductRestockRequest(BaseModel):
    product_id: int
    quantity: int = Field(..., gt=0, description="Quantity must be greater than 0")
    reason: Optional[str] = "Restock"


class InventoryAdjustmentRequest(BaseModel):
    quantity_available: Optional[int] = Field(None, ge=0)
    quantity_on_hand: Optional[int] = Field(None, ge=0)
    reason: Optional[str] = "Inventory Adjustment"
