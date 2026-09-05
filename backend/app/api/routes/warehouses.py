from typing import List, Dict, Any
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_roles
from app.models.user import User, Role
from app.schemas.warehouse import (
    WarehouseCreate,
    WarehouseUpdate,
    WarehouseResponse,
    WarehouseInventorySummaryResponse,
    WarehouseProductRestockRequest,
    InventoryAdjustmentRequest,
    InventoryResponse,
)
from app.services.warehouse_service import warehouse_service, inventory_service

router = APIRouter(prefix="/warehouses", tags=["Warehouses"])


@router.get("", response_model=List[WarehouseResponse])
def list_warehouses(
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.ADMIN, Role.SALES_MANAGER, Role.OPERATIONS)),
):
    """List all warehouses with current available inventory stock aggregated."""
    return warehouse_service.list_warehouses(db=db)


@router.get("/{warehouse_id}", response_model=WarehouseResponse)
def get_warehouse(
    warehouse_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.ADMIN, Role.SALES_MANAGER, Role.OPERATIONS)),
):
    """Get warehouse details by ID."""
    return warehouse_service.get_warehouse(db=db, warehouse_id=warehouse_id)


@router.post("", response_model=WarehouseResponse, status_code=status.HTTP_201_CREATED)
def create_warehouse(
    warehouse_in: WarehouseCreate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.ADMIN, Role.SALES_MANAGER)),
):
    """Create a new warehouse (Admin and Sales Manager only)."""
    wh = warehouse_service.create_warehouse(db=db, warehouse_in=warehouse_in, user_id=current_user.id)
    return warehouse_service.get_warehouse(db=db, warehouse_id=wh.id)


@router.patch("/{warehouse_id}", response_model=WarehouseResponse)
def update_warehouse(
    warehouse_id: int,
    warehouse_in: WarehouseUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.ADMIN, Role.SALES_MANAGER)),
):
    """Update warehouse details or activate/deactivate (Admin and Sales Manager only)."""
    wh = warehouse_service.update_warehouse(
        db=db, warehouse_id=warehouse_id, warehouse_in=warehouse_in, user_id=current_user.id
    )
    return warehouse_service.get_warehouse(db=db, warehouse_id=wh.id)


@router.post("/{warehouse_id}/activate", response_model=WarehouseResponse)
def activate_warehouse(
    warehouse_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.ADMIN, Role.SALES_MANAGER)),
):
    """Activate a warehouse (Admin and Sales Manager only)."""
    wh = warehouse_service.activate_warehouse(db=db, warehouse_id=warehouse_id, user_id=current_user.id)
    return warehouse_service.get_warehouse(db=db, warehouse_id=wh.id)


@router.post("/{warehouse_id}/deactivate", response_model=WarehouseResponse)
def deactivate_warehouse(
    warehouse_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.ADMIN, Role.SALES_MANAGER)),
):
    """Deactivate a warehouse (Admin and Sales Manager only)."""
    wh = warehouse_service.deactivate_warehouse(db=db, warehouse_id=warehouse_id, user_id=current_user.id)
    return warehouse_service.get_warehouse(db=db, warehouse_id=wh.id)


@router.delete("/{warehouse_id}")
def delete_warehouse(
    warehouse_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.ADMIN, Role.SALES_MANAGER)),
):
    """Safely delete a warehouse if it has no stock or orders (Admin and Sales Manager only)."""
    return warehouse_service.delete_warehouse(db=db, warehouse_id=warehouse_id, user_id=current_user.id)


@router.get("/{warehouse_id}/inventory")
def get_warehouse_inventory(
    warehouse_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.ADMIN, Role.SALES_MANAGER, Role.OPERATIONS)),
):
    """List inventory items for a specific warehouse."""
    return inventory_service.list_inventory(db=db, warehouse_id=warehouse_id)


@router.get("/{warehouse_id}/inventory/summary", response_model=WarehouseInventorySummaryResponse)
def get_warehouse_inventory_summary(
    warehouse_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.ADMIN, Role.SALES_MANAGER, Role.OPERATIONS)),
):
    """Get warehouse inventory grouped by product category with dynamic category totals."""
    return inventory_service.get_warehouse_inventory_summary(db=db, warehouse_id=warehouse_id)


@router.post("/{warehouse_id}/inventory/restock", response_model=InventoryResponse)
def restock_warehouse_product(
    warehouse_id: int,
    restock_in: WarehouseProductRestockRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.ADMIN, Role.SALES_MANAGER, Role.OPERATIONS)),
):
    """Restock a product in a warehouse."""
    return inventory_service.restock_by_product(
        db=db,
        warehouse_id=warehouse_id,
        product_id=restock_in.product_id,
        quantity=restock_in.quantity,
        reason=restock_in.reason,
        user_id=current_user.id,
    )


@router.patch("/{warehouse_id}/inventory/{product_id}", response_model=InventoryResponse)
def adjust_warehouse_inventory(
    warehouse_id: int,
    product_id: int,
    adj_in: InventoryAdjustmentRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.ADMIN, Role.SALES_MANAGER)),
):
    """Adjust inventory balance for a product in a warehouse."""
    return inventory_service.adjust_inventory(
        db=db,
        warehouse_id=warehouse_id,
        product_id=product_id,
        quantity_available=adj_in.quantity_available,
        quantity_on_hand=adj_in.quantity_on_hand,
        reason=adj_in.reason,
        user_id=current_user.id,
    )
