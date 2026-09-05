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

    def activate_warehouse(self, db: Session, warehouse_id: int, user_id: Optional[int] = None) -> Warehouse:
        wh = db.query(Warehouse).filter(Warehouse.id == warehouse_id).first()
        if not wh:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "WAREHOUSE_NOT_FOUND", "message": f"Warehouse {warehouse_id} not found"},
            )
        old_val = wh.is_active
        wh.is_active = True
        wh.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(wh)

        audit = AuditLog(
            user_id=user_id,
            entity_type="WAREHOUSE",
            entity_id=wh.id,
            action="WAREHOUSE_ACTIVATED",
            old_value=json.dumps({"is_active": old_val}),
            new_value=json.dumps({"is_active": True}),
        )
        db.add(audit)
        db.commit()
        return wh

    def deactivate_warehouse(self, db: Session, warehouse_id: int, user_id: Optional[int] = None) -> Warehouse:
        wh = db.query(Warehouse).filter(Warehouse.id == warehouse_id).first()
        if not wh:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "WAREHOUSE_NOT_FOUND", "message": f"Warehouse {warehouse_id} not found"},
            )
        old_val = wh.is_active
        wh.is_active = False
        wh.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(wh)

        audit = AuditLog(
            user_id=user_id,
            entity_type="WAREHOUSE",
            entity_id=wh.id,
            action="WAREHOUSE_DEACTIVATED",
            old_value=json.dumps({"is_active": old_val}),
            new_value=json.dumps({"is_active": False}),
        )
        db.add(audit)
        db.commit()
        return wh

    def delete_warehouse(self, db: Session, warehouse_id: int, user_id: Optional[int] = None) -> Dict[str, Any]:
        wh = db.query(Warehouse).filter(Warehouse.id == warehouse_id).first()
        if not wh:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "WAREHOUSE_NOT_FOUND", "message": f"Warehouse {warehouse_id} not found"},
            )

        # Check if warehouse has active stock
        total_stock = sum(
            (inv.quantity_available or 0) + (inv.quantity_allocated or 0) for inv in wh.inventory_items
        )
        if total_stock > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "CANNOT_DELETE_WAREHOUSE",
                    "message": f"Cannot delete warehouse '{wh.name}' with existing inventory stock ({total_stock} units).",
                },
            )

        # Check if warehouse is referenced in fulfillment splits
        from app.models.order import FulfillmentSplit
        split_count = db.query(FulfillmentSplit).filter(FulfillmentSplit.warehouse_id == warehouse_id).count()
        if split_count > 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={
                    "code": "CANNOT_DELETE_WAREHOUSE",
                    "message": f"Cannot delete warehouse '{wh.name}' referenced in {split_count} fulfillment splits.",
                },
            )

        # Clean up 0-quantity inventory rows if any
        for inv in wh.inventory_items:
            db.delete(inv)

        wh_name = wh.name
        db.delete(wh)
        db.commit()

        audit = AuditLog(
            user_id=user_id,
            entity_type="WAREHOUSE",
            entity_id=warehouse_id,
            action="WAREHOUSE_DELETED",
            old_value=json.dumps({"name": wh_name}),
            new_value=None,
        )
        db.add(audit)
        db.commit()
        return {"message": f"Warehouse '{wh_name}' deleted successfully", "id": warehouse_id}


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

    def restock_by_product(
        self,
        db: Session,
        warehouse_id: int,
        product_id: int,
        quantity: int,
        reason: Optional[str] = "Restock",
        user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        if quantity <= 0:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "INVALID_QUANTITY", "message": "Restock quantity must be greater than zero"},
            )

        wh = db.query(Warehouse).filter(Warehouse.id == warehouse_id).first()
        if not wh:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "WAREHOUSE_NOT_FOUND", "message": f"Warehouse {warehouse_id} not found"},
            )

        prod = db.query(Product).filter(Product.id == product_id).first()
        if not prod:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "PRODUCT_NOT_FOUND", "message": f"Product {product_id} not found"},
            )
        if not prod.is_active:
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail={"code": "PRODUCT_INACTIVE", "message": f"Cannot restock inactive product '{prod.name}'"},
            )

        inv = (
            db.query(Inventory)
            .filter(Inventory.warehouse_id == warehouse_id, Inventory.product_id == product_id)
            .first()
        )

        now_utc = datetime.now(timezone.utc)
        if inv:
            current_on_hand = inv.quantity_on_hand if inv.quantity_on_hand is not None else inv.quantity_available
            current_avail = inv.quantity_available
            inv.quantity_on_hand = current_on_hand + quantity
            inv.quantity_available = current_avail + quantity
            inv.updated_at = now_utc
            action = "INVENTORY_RESTOCKED"
            old_val = {"available": current_avail, "on_hand": current_on_hand}
        else:
            inv = Inventory(
                warehouse_id=warehouse_id,
                product_id=product_id,
                quantity_on_hand=quantity,
                quantity_available=quantity,
                quantity_allocated=0,
                updated_at=now_utc,
            )
            db.add(inv)
            action = "INVENTORY_STOCK_ADDED"
            old_val = None

        db.commit()
        db.refresh(inv)

        audit = AuditLog(
            user_id=user_id,
            entity_type="INVENTORY",
            entity_id=inv.id,
            action=action,
            old_value=json.dumps(old_val) if old_val else None,
            new_value=json.dumps({
                "warehouse_id": warehouse_id,
                "warehouse_name": wh.name,
                "product_id": product_id,
                "product_name": prod.name,
                "quantity_added": quantity,
                "new_available": inv.quantity_available,
                "new_on_hand": inv.quantity_on_hand,
                "reason": reason or "Restock",
            }),
        )
        db.add(audit)
        db.commit()

        return self.get_inventory(db, inv.id)

    def adjust_inventory(
        self,
        db: Session,
        warehouse_id: int,
        product_id: int,
        quantity_available: Optional[int] = None,
        quantity_on_hand: Optional[int] = None,
        reason: Optional[str] = "Inventory Adjustment",
        user_id: Optional[int] = None,
    ) -> Dict[str, Any]:
        inv = (
            db.query(Inventory)
            .filter(Inventory.warehouse_id == warehouse_id, Inventory.product_id == product_id)
            .first()
        )
        if not inv:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "INVENTORY_NOT_FOUND", "message": f"Inventory for product {product_id} in warehouse {warehouse_id} not found"},
            )

        old_val = {
            "available": inv.quantity_available,
            "on_hand": inv.quantity_on_hand,
            "allocated": inv.quantity_allocated,
        }

        if quantity_available is not None:
            if quantity_available < 0:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"code": "INVALID_QUANTITY", "message": "Available stock cannot be negative"})
            inv.quantity_available = quantity_available

        if quantity_on_hand is not None:
            if quantity_on_hand < 0:
                raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"code": "INVALID_QUANTITY", "message": "On-hand stock cannot be negative"})
            inv.quantity_on_hand = quantity_on_hand

        inv.updated_at = datetime.now(timezone.utc)
        db.commit()
        db.refresh(inv)

        audit = AuditLog(
            user_id=user_id,
            entity_type="INVENTORY",
            entity_id=inv.id,
            action="INVENTORY_ADJUSTED",
            old_value=json.dumps(old_val),
            new_value=json.dumps({
                "available": inv.quantity_available,
                "on_hand": inv.quantity_on_hand,
                "reason": reason or "Adjustment",
            }),
        )
        db.add(audit)
        db.commit()
        return self.get_inventory(db, inv.id)

    def get_warehouse_inventory_summary(self, db: Session, warehouse_id: int) -> Dict[str, Any]:
        wh = db.query(Warehouse).filter(Warehouse.id == warehouse_id).first()
        if not wh:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail={"code": "WAREHOUSE_NOT_FOUND", "message": f"Warehouse {warehouse_id} not found"},
            )

        inventories = (
            db.query(Inventory)
            .options(
                joinedload(Inventory.product).joinedload(Product.category),
            )
            .filter(Inventory.warehouse_id == warehouse_id)
            .order_by(Inventory.id.asc())
            .all()
        )

        # Group by category
        categories_map: Dict[Any, Dict[str, Any]] = {}

        total_warehouse_units = 0
        low_stock_count = 0

        for inv in inventories:
            prod = inv.product
            if not prod:
                continue

            cat = prod.category
            cat_id = cat.id if cat else None
            cat_name = cat.name if cat else "Uncategorized"

            if cat_id not in categories_map:
                categories_map[cat_id] = {
                    "category_id": cat_id,
                    "category_name": cat_name,
                    "total_units": 0,
                    "products": [],
                }

            ft = getattr(prod, "fulfillment_type", "PHYSICAL")
            status_str = self._compute_stock_status(ft, inv.quantity_available)

            if 0 < inv.quantity_available < 10 and ft != "SERVICE":
                low_stock_count += 1

            # Only count actual available inventory towards category totals
            categories_map[cat_id]["total_units"] += inv.quantity_available
            total_warehouse_units += inv.quantity_available

            categories_map[cat_id]["products"].append({
                "product_id": prod.id,
                "product_name": prod.name,
                "sku": prod.sku,
                "fulfillment_type": ft,
                "quantity_available": inv.quantity_available,
                "quantity_reserved": inv.quantity_allocated or 0,
                "status": status_str,
            })

        categories_list = list(categories_map.values())
        # Sort categories by name
        categories_list.sort(key=lambda c: c["category_name"])

        return {
            "warehouse_id": wh.id,
            "warehouse_name": wh.name,
            "location": wh.location,
            "status": "ACTIVE",
            "total_units": total_warehouse_units,
            "total_products": len(inventories),
            "total_categories": len(categories_list),
            "low_stock_items": low_stock_count,
            "categories": categories_list,
        }

    def list_low_stock(self, db: Session, warehouse_id: Optional[int] = None, threshold: int = 10) -> List[Dict[str, Any]]:
        query = (
            db.query(Inventory)
            .options(
                joinedload(Inventory.warehouse),
                joinedload(Inventory.product).joinedload(Product.category),
            )
            .filter(Inventory.quantity_available < threshold)
        )
        if warehouse_id is not None:
            query = query.filter(Inventory.warehouse_id == warehouse_id)

        items = query.order_by(Inventory.quantity_available.asc()).all()
        results = []
        for inv in items:
            prod = inv.product
            wh = inv.warehouse
            cat = prod.category if prod else None
            ft = getattr(prod, "fulfillment_type", "PHYSICAL") if prod else "PHYSICAL"
            if ft == "SERVICE":
                continue # Services don't trigger physical low-stock alerts
            results.append({
                "id": inv.id,
                "warehouse_id": inv.warehouse_id,
                "warehouse_name": wh.name if wh else None,
                "product_id": inv.product_id,
                "product_name": prod.name if prod else None,
                "product_sku": prod.sku if prod else None,
                "category_name": cat.name if cat else "Uncategorized",
                "fulfillment_type": ft,
                "quantity_available": inv.quantity_available,
                "quantity_on_hand": inv.quantity_on_hand or inv.quantity_available,
                "quantity_allocated": inv.quantity_allocated or 0,
                "stock_status": self._compute_stock_status(ft, inv.quantity_available),
                "updated_at": inv.updated_at,
            })
        return results


warehouse_service = WarehouseService()
inventory_service = InventoryService()
