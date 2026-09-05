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
        
        if order.status != OrderStatus.PENDING:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"code": "INVALID_STATE", "message": "Order must be PENDING to suggest fulfillment"})

        result = {
            "order_id": order.id,
            "lines": []
        }

        for line in order.lines:
            if line.line_type.value != "ONE_TIME":
                continue # Only physical ONE_TIME items need inventory fulfillment
                
            requested_quantity = line.quantity
            allocations = []
            
            # Fetch inventory available across all active warehouses for this product
            inventories = db.query(Inventory).join(Warehouse).filter(
                Inventory.product_id == line.product_id,
                Warehouse.is_active == True,
                Inventory.quantity_available > 0
            ).all()
            
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

    def confirm_fulfillment(self, db: Session, order_id: int, user_id: int, allocations_input: List[Dict[str, Any]] = None) -> Order:
        order = db.query(Order).filter(Order.id == order_id).first()
        if not order:
            raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail={"code": "NOT_FOUND", "message": "Order not found"})

        if order.status != OrderStatus.PENDING:
            raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail={"code": "INVALID_STATE", "message": "Order must be PENDING to confirm fulfillment"})

        if allocations_input is None:
            # If no allocations provided, use suggestion logic
            suggestion = self.suggest_fulfillment(db, order_id)
            allocations_input = suggestion["lines"]

        for line_data in allocations_input:
            product_id = line_data["product_id"]
            # Find the corresponding order line
            order_line = next((l for l in order.lines if l.product_id == product_id and l.line_type.value == "ONE_TIME"), None)
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
                # We can store backordered items against a dummy warehouse or handle it via a special status on the split
                # But typically we might just not create a split, or create one with BACKORDERED status without a warehouse. 
                # Our schema requires warehouse_id. For MVP, we might assign it to a default or just let it be.
                # Actually, the requirement says "The API should clearly expose requested_quantity, allocated, backordered".
                pass
                
        order.status = OrderStatus.CONFIRMED
        
        audit = AuditLog(
            user_id=user_id,
            entity_type="Order",
            entity_id=order.id,
            action="FULFILLMENT_CONFIRMED",
            new_value="Fulfillment confirmed"
        )
        db.add(audit)
        
        db.commit()
        db.refresh(order)
        return order

fulfillment_service = FulfillmentService()
