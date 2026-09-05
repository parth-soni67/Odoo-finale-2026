from typing import List, Dict, Any, Optional
from sqlalchemy.orm import Session
from fastapi import HTTPException, status
from app.models.order import Order, OrderLine, OrderStatus, FulfillmentSplit, FulfillmentSplitStatus
from app.models.warehouse import Warehouse, Inventory
from app.models.audit import AuditLog

class FulfillmentService:
    def suggest_fulfillment(self, db: Session, order_id: int) -> Dict[str, Any]:
        order = db.query(Order).filter(Order.id == order_id).first()
        if not order:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": "NOT_FOUND", "message": "Order not found"})
        
        if order.status not in (OrderStatus.PENDING, OrderStatus.PROCESSING):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"code": "INVALID_STATE", "message": "Order must be PENDING or PROCESSING to suggest fulfillment"})

        result = {
            "order_id": order.id,
            "lines": []
        }

        for line in order.lines:
            line_type_val = getattr(line.line_type, "value", str(line.line_type))
            if line_type_val != "ONE_TIME":
                continue # Only physical ONE_TIME items need inventory fulfillment
                
            requested_quantity = line.quantity
            allocations = []
            
            # Fetch inventory available across all active warehouses for this product
            inventories = db.query(Inventory).join(Warehouse).filter(
                Inventory.product_id == line.product_id,
                Warehouse.is_active == True,
                Inventory.quantity_available > 0
            ).order_by(Warehouse.id.asc()).all()
            
            remaining = requested_quantity
            
            for inv in inventories:
                if remaining <= 0:
                    break
                
                allocate = min(inv.quantity_available, remaining)
                allocations.append({
                    "warehouse_id": inv.warehouse.id,
                    "warehouse": inv.warehouse.name,
                    "quantity": allocate
                })
                remaining -= allocate
                
            result["lines"].append({
                "product_id": line.product_id,
                "requested_quantity": requested_quantity,
                "allocations": allocations,
                "backordered_quantity": remaining
            })
            
        return result

    def auto_allocate_order(self, db: Session, order: Order, user_id: Optional[int] = None) -> Order:
        """
        Automatically allocates available inventory across active warehouses for ONE_TIME physical lines.
        Idempotent: skips order lines that already have fulfillment splits so inventory is never deducted twice.
        """
        allocated_any = False
        has_physical_lines = False

        for line in order.lines:
            line_type_val = getattr(line.line_type, "value", str(line.line_type))
            if line_type_val != "ONE_TIME":
                continue

            has_physical_lines = True

            # Idempotency check: if line already has fulfillment splits, do not re-allocate or double deduct
            existing_splits = db.query(FulfillmentSplit).filter(FulfillmentSplit.order_line_id == line.id).all()
            if existing_splits:
                allocated_any = True
                continue

            requested_quantity = line.quantity
            remaining = requested_quantity

            # Fetch inventory available across all active warehouses
            inventories = (
                db.query(Inventory)
                .join(Warehouse, Inventory.warehouse_id == Warehouse.id)
                .filter(
                    Inventory.product_id == line.product_id,
                    Warehouse.is_active == True,
                    Inventory.quantity_available > 0,
                )
                .order_by(Warehouse.id.asc())
                .all()
            )

            for inv in inventories:
                if remaining <= 0:
                    break
                allocate = min(inv.quantity_available, remaining)
                inv.quantity_available -= allocate
                split = FulfillmentSplit(
                    order_line_id=line.id,
                    warehouse_id=inv.warehouse_id,
                    quantity_allocated=allocate,
                    status=FulfillmentSplitStatus.ALLOCATED,
                )
                db.add(split)
                remaining -= allocate
                allocated_any = True

        if has_physical_lines:
            if allocated_any:
                order.status = OrderStatus.PROCESSING
            else:
                # 0 inventory was available, entirely backordered
                order.status = OrderStatus.PENDING
        else:
            # Only recurring lines
            order.status = OrderStatus.PROCESSING

        if allocated_any and user_id:
            audit = AuditLog(
                user_id=user_id,
                entity_type="Order",
                entity_id=order.id,
                action="INVENTORY_ALLOCATED",
                new_value=f"Automated warehouse allocation completed for order {order.order_number}",
            )
            db.add(audit)

        db.flush()
        return order

    def confirm_fulfillment(self, db: Session, order_id: int, user_id: int, allocations_input: List[Dict[str, Any]] = None) -> Order:
        order = db.query(Order).filter(Order.id == order_id).first()
        if not order:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": "NOT_FOUND", "message": "Order not found"})

        if order.status not in (OrderStatus.PENDING, OrderStatus.PROCESSING):
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"code": "INVALID_STATE", "message": "Order must be PENDING or PROCESSING to confirm fulfillment"})

        # Check if already fulfilled / splits already exist
        has_existing_splits = any(len(line.fulfillment_splits) > 0 for line in order.lines)

        if not has_existing_splits:
            if allocations_input is None:
                # If no allocations provided, use suggestion logic
                suggestion = self.suggest_fulfillment(db, order_id)
                allocations_input = suggestion["lines"]

            for line_data in allocations_input:
                product_id = line_data["product_id"]
                # Find the corresponding order line
                order_line = next((l for l in order.lines if l.product_id == product_id and getattr(l.line_type, "value", str(l.line_type)) == "ONE_TIME"), None)
                if not order_line:
                    continue
                    
                allocations = line_data.get("allocations", [])
                for alloc in allocations:
                    warehouse_id = alloc["warehouse_id"]
                    quantity = alloc["quantity"]
                    
                    # Verify inventory
                    inv = db.query(Inventory).filter(
                        Inventory.product_id == product_id,
                        Inventory.warehouse_id == warehouse_id
                    ).first()
                    
                    if not inv or inv.quantity_available < quantity:
                        raise HTTPException(
                            status_code=status.HTTP_400_BAD_REQUEST,
                            detail={"code": "INSUFFICIENT_INVENTORY", "message": f"Not enough inventory in warehouse {warehouse_id} for product {product_id}"}
                        )
                    
                    # Reduce inventory
                    inv.quantity_available -= quantity
                    
                    # Create FulfillmentSplit
                    split = FulfillmentSplit(
                        order_line_id=order_line.id,
                        warehouse_id=warehouse_id,
                        quantity_allocated=quantity,
                        status=FulfillmentSplitStatus.ALLOCATED
                    )
                    db.add(split)
                
                backordered_qty = line_data.get("backordered_quantity", 0)
                if backordered_qty > 0:
                    pass

        db.commit()
        db.refresh(order)

        # Activate order and any product-defined subscriptions
        from app.services.order_service import order_service
        order = order_service.activate_order(db, order.id, user_id)
        return order

fulfillment_service = FulfillmentService()
