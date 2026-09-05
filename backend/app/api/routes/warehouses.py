from typing import List
from fastapi import APIRouter, Depends, status
from sqlalchemy.orm import Session

from app.core.database import get_db
from app.core.dependencies import require_roles
from app.models.user import User, Role
from app.schemas.warehouse import WarehouseCreate, WarehouseUpdate, WarehouseResponse
from app.services.warehouse_service import warehouse_service

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


@router.get("/{warehouse_id}/inventory")
def get_warehouse_inventory(
    warehouse_id: int,
    db: Session = Depends(get_db),
    current_user: User = Depends(require_roles(Role.ADMIN, Role.SALES_MANAGER, Role.OPERATIONS)),
):
    """List inventory items for a specific warehouse."""
    from app.services.warehouse_service import inventory_service
    return inventory_service.list_inventory(db=db, warehouse_id=warehouse_id)
