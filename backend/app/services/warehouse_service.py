import json
from datetime import datetime, timezone
from typing import List, Optional, Dict, Any
from sqlalchemy.orm import Session, joinedload
from fastapi import HTTPException, status

from app.models.warehouse import Warehouse, Inventory
from app.models.product import Product, ProductCategory
from app.models.audit import AuditLog
from app.schemas.warehouse import (
    WarehouseCreate,
    WarehouseUpdate,
    WarehouseResponse,
    InventoryStockCreate,
    InventoryRestockCreate,
    InventoryResponse,
)


class WarehouseService:
    def list_warehouses(self, db: Session, include_inactive: bool = True) -> List[Dict[str, Any]]:
        query = db.query(Warehouse)
        if not include_inactive:
            query = query.filter(Warehouse.is_active == True)
        warehouses = query.order_by(Warehouse.id.asc()).all()

        results = []
        for wh in warehouses:
            available_stock = sum(inv.quantity_available for inv in wh.inventory_items)
            results.append({
                "id": wh.id,
                "name": wh.name,
                "location": wh.location,
                "is_active": wh.is_active,
                "available_stock": available_stock,
                "created_at": wh.created_at,
                "updated_at": wh.updated_at,
            })
        return results

    def get_warehouse(self, db: Session, warehouse_id: int) -> Dict[str, Any]:
        wh = db.query(Warehouse).filter(Warehouse.id == warehouse_id).first()
        if not wh:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "WAREHOUSE_NOT_FOUND", "message": f"Warehouse {warehouse_id} not found"},
            )
        available_stock = sum(inv.quantity_available for inv in wh.inventory_items)
        return {
            "id": wh.id,
            "name": wh.name,
            "location": wh.location,
            "is_active": wh.is_active,
            "available_stock": available_stock,
            "created_at": wh.created_at,
            "updated_at": wh.updated_at,
        }

    def create_warehouse(self, db: Session, warehouse_in: WarehouseCreate, user_id: Optional[int] = None) -> Warehouse:
        existing = db.query(Warehouse).filter(Warehouse.name == warehouse_in.name).first()
        if existing:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "WAREHOUSE_EXISTS", "message": f"Warehouse '{warehouse_in.name}' already exists"},
            )

        wh = Warehouse(
            name=warehouse_in.name,
            location=warehouse_in.location,
            is_active=warehouse_in.is_active,
            created_at=datetime.now(timezone.utc),
            updated_at=datetime.now(timezone.utc),
        )
        db.add(wh)
        db.commit()
        db.refresh(wh)

        audit = AuditLog(
            user_id=user_id,
            entity_type="WAREHOUSE",
            entity_id=wh.id,
            action="WAREHOUSE_CREATED",
            old_value=None,
            new_value=json.dumps({"name": wh.name, "location": wh.location, "is_active": wh.is_active}),
        )
        db.add(audit)
        db.commit()
        return wh

    def update_warehouse(
        self, db: Session, warehouse_id: int, warehouse_in: WarehouseUpdate, user_id: Optional[int] = None
    ) -> Warehouse:
        wh = db.query(Warehouse).filter(Warehouse.id == warehouse_id).first()
        if not wh:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "WAREHOUSE_NOT_FOUND", "message": f"Warehouse {warehouse_id} not found"},
            )

        old_val = {"name": wh.name, "location": wh.location, "is_active": wh.is_active}
        update_dict = warehouse_in.model_dump(exclude_unset=True)
        was_active = wh.is_active

        for key, val in update_dict.items():
            setattr(wh, key, val)
        wh.updated_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(wh)

        action = "WAREHOUSE_DEACTIVATED" if (was_active and not wh.is_active) else "WAREHOUSE_UPDATED"
        audit = AuditLog(
            user_id=user_id,
            entity_type="WAREHOUSE",
            entity_id=wh.id,
            action=action,
            old_value=json.dumps(old_val),
            new_value=json.dumps({"name": wh.name, "location": wh.location, "is_active": wh.is_active}),
        )
        db.add(audit)
        db.commit()
        return wh


class InventoryService:
    def _compute_stock_status(self, fulfillment_type: str, qty_available: int) -> str:
        ft = (fulfillment_type or "PHYSICAL").upper()
        if ft == "DIGITAL":
            return "DIGITAL"
        if ft == "SERVICE":
            return "SERVICE"
        if qty_available <= 0:
            return "OUT OF STOCK"
        if qty_available < 10:
            return "LOW STOCK"
        return "IN STOCK"

    def list_inventory(
        self,
        db: Session,
        warehouse_id: Optional[int] = None,
        product_id: Optional[int] = None,
        category_id: Optional[int] = None,
    ) -> List[Dict[str, Any]]:
        query = (
            db.query(Inventory)
            .options(
                joinedload(Inventory.warehouse),
                joinedload(Inventory.product).joinedload(Product.category),
            )
        )
        if warehouse_id is not None:
            query = query.filter(Inventory.warehouse_id == warehouse_id)
        if product_id is not None:
            query = query.filter(Inventory.product_id == product_id)

        items = query.order_by(Inventory.id.desc()).all()

        results = []
        for inv in items:
            prod = inv.product
            wh = inv.warehouse
            cat = prod.category if prod else None
            ft = getattr(prod, "fulfillment_type", "PHYSICAL") if prod else "PHYSICAL"

            if category_id is not None and (not cat or cat.id != category_id):
                continue

            # Ensure quantity_on_hand and quantity_allocated are consistent
            on_hand = inv.quantity_on_hand if inv.quantity_on_hand is not None else inv.quantity_available
            allocated = inv.quantity_allocated if inv.quantity_allocated is not None else 0

            status_str = self._compute_stock_status(ft, inv.quantity_available)

            results.append({
                "id": inv.id,
                "warehouse_id": inv.warehouse_id,
                "warehouse_name": wh.name if wh else f"Warehouse #{inv.warehouse_id}",
                "warehouse_location": wh.location if wh else None,
                "product_id": inv.product_id,
                "product_name": prod.name if prod else f"Product #{inv.product_id}",
                "product_sku": prod.sku if prod else None,
                "category_name": cat.name if cat else "Uncategorized",
                "fulfillment_type": ft,
                "quantity_on_hand": on_hand,
                "quantity_available": inv.quantity_available,
                "quantity_allocated": allocated,
                "stock_status": status_str,
                "updated_at": inv.updated_at,
            })
        return results

    def get_inventory(self, db: Session, inventory_id: int) -> Dict[str, Any]:
        inv = (
            db.query(Inventory)
            .options(
                joinedload(Inventory.warehouse),
                joinedload(Inventory.product).joinedload(Product.category),
            )
            .filter(Inventory.id == inventory_id)
            .first()
        )
        if not inv:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "INVENTORY_NOT_FOUND", "message": f"Inventory record {inventory_id} not found"},
            )
        prod = inv.product
        wh = inv.warehouse
        cat = prod.category if prod else None
        ft = getattr(prod, "fulfillment_type", "PHYSICAL") if prod else "PHYSICAL"
        on_hand = inv.quantity_on_hand if inv.quantity_on_hand is not None else inv.quantity_available
        allocated = inv.quantity_allocated if inv.quantity_allocated is not None else 0

        return {
            "id": inv.id,
            "warehouse_id": inv.warehouse_id,
            "warehouse_name": wh.name if wh else f"Warehouse #{inv.warehouse_id}",
            "warehouse_location": wh.location if wh else None,
            "product_id": inv.product_id,
            "product_name": prod.name if prod else f"Product #{inv.product_id}",
            "product_sku": prod.sku if prod else None,
            "category_name": cat.name if cat else "Uncategorized",
            "fulfillment_type": ft,
            "quantity_on_hand": on_hand,
            "quantity_available": inv.quantity_available,
            "quantity_allocated": allocated,
            "stock_status": self._compute_stock_status(ft, inv.quantity_available),
            "updated_at": inv.updated_at,
        }

    def add_stock(self, db: Session, stock_in: InventoryStockCreate, user_id: Optional[int] = None) -> Dict[str, Any]:
        if stock_in.quantity <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "INVALID_QUANTITY", "message": "Stock quantity must be greater than zero"},
            )

        wh = db.query(Warehouse).filter(Warehouse.id == stock_in.warehouse_id).first()
        if not wh:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "WAREHOUSE_NOT_FOUND", "message": f"Warehouse {stock_in.warehouse_id} not found"},
            )
        if not wh.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "WAREHOUSE_INACTIVE", "message": f"Cannot add stock to inactive warehouse '{wh.name}'"},
            )

        prod = db.query(Product).filter(Product.id == stock_in.product_id).first()
        if not prod:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "PRODUCT_NOT_FOUND", "message": f"Product {stock_in.product_id} not found"},
            )

        now_utc = datetime.now(timezone.utc)
        # Check if record for same warehouse + same product already exists
        inv = (
            db.query(Inventory)
            .filter(Inventory.warehouse_id == stock_in.warehouse_id, Inventory.product_id == stock_in.product_id)
            .first()
        )

        if inv:
            # Update existing row
            current_on_hand = inv.quantity_on_hand if inv.quantity_on_hand is not None else inv.quantity_available
            inv.quantity_on_hand = current_on_hand + stock_in.quantity
            inv.quantity_available = inv.quantity_available + stock_in.quantity
            inv.updated_at = now_utc
        else:
            inv = Inventory(
                warehouse_id=stock_in.warehouse_id,
                product_id=stock_in.product_id,
                quantity_on_hand=stock_in.quantity,
                quantity_available=stock_in.quantity,
                quantity_allocated=0,
                updated_at=now_utc,
            )
            db.add(inv)

        db.commit()
        db.refresh(inv)

        audit = AuditLog(
            user_id=user_id,
            entity_type="INVENTORY",
            entity_id=inv.id,
            action="INVENTORY_STOCK_ADDED",
            old_value=None,
            new_value=json.dumps({
                "warehouse_id": inv.warehouse_id,
                "product_id": inv.product_id,
                "quantity_added": stock_in.quantity,
                "new_available": inv.quantity_available,
                "new_on_hand": inv.quantity_on_hand,
                "reason": stock_in.reason or "Initial Stock",
            }),
        )
        db.add(audit)
        db.commit()

        return self.get_inventory(db, inv.id)

    def restock(
        self, db: Session, inventory_id: int, restock_in: InventoryRestockCreate, user_id: Optional[int] = None
    ) -> Dict[str, Any]:
        if restock_in.quantity <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "INVALID_QUANTITY", "message": "Restock quantity must be greater than zero"},
            )

        inv = db.query(Inventory).filter(Inventory.id == inventory_id).first()
        if not inv:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "INVENTORY_NOT_FOUND", "message": f"Inventory record {inventory_id} not found"},
            )

        current_on_hand = inv.quantity_on_hand if inv.quantity_on_hand is not None else inv.quantity_available
        current_avail = inv.quantity_available

        inv.quantity_on_hand = current_on_hand + restock_in.quantity
        inv.quantity_available = current_avail + restock_in.quantity
        inv.updated_at = datetime.now(timezone.utc)

        db.commit()
        db.refresh(inv)

        audit = AuditLog(
            user_id=user_id,
            entity_type="INVENTORY",
            entity_id=inv.id,
            action="INVENTORY_RESTOCKED",
            old_value=json.dumps({"available": current_avail, "on_hand": current_on_hand}),
            new_value=json.dumps({
                "quantity_restocked": restock_in.quantity,
                "new_available": inv.quantity_available,
                "new_on_hand": inv.quantity_on_hand,
                "reason": restock_in.reason or "Restock",
            }),
        )
        db.add(audit)
        db.commit()

        return self.get_inventory(db, inv.id)


warehouse_service = WarehouseService()
inventory_service = InventoryService()
