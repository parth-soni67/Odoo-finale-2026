from typing import List, Optional
from fastapi import APIRouter, Depends, Query, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_roles
from app.models.user import User, Role
from app.schemas.warehouse import (
    InventoryStockCreate,
    InventoryRestockCreate,
    InventoryResponse,
)
from app.services.warehouse_service import inventory_service

router = APIRouter(prefix="/inventory", tags=["Inventory"])


@router.get("", response_model=List[InventoryResponse])
def list_inventory(
    warehouse_id: Optional[int] = Query(None, description="Filter by warehouse ID"),
    product_id: Optional[int] = Query(None, description="Filter by product ID"),
    category_id: Optional[int] = Query(None, description="Filter by category ID"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.ADMIN, Role.SALES_MANAGER, Role.OPERATIONS)),
):
    """List inventory records across warehouses with on hand, available, and allocated balances."""
    return inventory_service.list_inventory(
        db=db, warehouse_id=warehouse_id, product_id=product_id, category_id=category_id
    )


@router.get("/low-stock", response_model=List[InventoryResponse])
def get_low_stock_inventory(
    warehouse_id: Optional[int] = Query(None, description="Filter by warehouse ID"),
    threshold: int = Query(10, description="Low stock threshold"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.ADMIN, Role.SALES_MANAGER, Role.OPERATIONS)),
):
    """List low-stock and out-of-stock items across warehouses."""
    return inventory_service.list_low_stock(db=db, warehouse_id=warehouse_id, threshold=threshold)


@router.get("/{inventory_id}", response_model=InventoryResponse)
def get_inventory(
    inventory_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.ADMIN, Role.SALES_MANAGER, Role.OPERATIONS)),
):
    """Retrieve details for a specific inventory record."""
    return inventory_service.get_inventory(db=db, inventory_id=inventory_id)


@router.post("/stock", response_model=InventoryResponse, status_code=status.HTTP_201_CREATED)
def add_inventory_stock(
    stock_in: InventoryStockCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.ADMIN, Role.SALES_MANAGER, Role.OPERATIONS)),
):
    """Add initial stock or new stock to a warehouse for a product (Admin, Sales Manager, Operations)."""
    return inventory_service.add_stock(db=db, stock_in=stock_in, user_id=current_user.id)


@router.post("/restock", response_model=InventoryResponse)
def restock_inventory(
    restock_in: InventoryRestockCreate,
    inventory_id: int = Query(..., description="The inventory record ID to restock"),
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.ADMIN, Role.SALES_MANAGER, Role.OPERATIONS)),
):
    """Restock an existing inventory record by adding to on hand and available quantities."""
    return inventory_service.restock(db=db, inventory_id=inventory_id, restock_in=restock_in, user_id=current_user.id)
