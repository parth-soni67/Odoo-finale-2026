import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.user import User, Role
from app.models.warehouse import Warehouse, Inventory
from app.models.product import Product, ProductCategory
from app.models.order import Order, OrderLine, OrderStatus, FulfillmentSplit
from app.models.quote import Quote, QuoteLine, QuoteStatus


def get_auth_headers(client: TestClient, email: str, password: str = "Demo1234!") -> dict:
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, f"Login failed for {email}: {resp.text}"
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# 1. Create warehouse
def test_01_create_warehouse(client: TestClient):
    mgr_headers = get_auth_headers(client, "salesmgr@dealflow360.internal")
    resp = client.post(
        "/api/warehouses",
        json={"name": "Bengaluru Tech Hub", "location": "Bengaluru, India", "is_active": True},
        headers=mgr_headers,
    )
    assert resp.status_code == 201
    data = resp.json()
    assert data["name"] == "Bengaluru Tech Hub"
    assert data["location"] == "Bengaluru, India"
    assert data["is_active"] is True


# 2. Unauthorized warehouse creation (Sales Rep & Customer blocked)
def test_02_unauthorized_warehouse_creation(client: TestClient):
    rep_headers = get_auth_headers(client, "salesrep@dealflow360.internal")
    cust_headers = get_auth_headers(client, "customer@acmecorp.com")

    resp_rep = client.post(
        "/api/warehouses",
        json={"name": "Rep Illegal WH", "location": "Nowhere"},
        headers=rep_headers,
    )
    assert resp_rep.status_code == 403

    resp_cust = client.post(
        "/api/warehouses",
        json={"name": "Customer Illegal WH", "location": "Nowhere"},
        headers=cust_headers,
    )
    assert resp_cust.status_code == 403


# 3. Get warehouse
def test_03_get_warehouse(client: TestClient):
    mgr_headers = get_auth_headers(client, "salesmgr@dealflow360.internal")
    resp = client.get("/api/warehouses/1", headers=mgr_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["id"] == 1
    assert "name" in data
    assert "available_stock" in data


# 4. Add inventory
def test_04_add_inventory(client: TestClient):
    mgr_headers = get_auth_headers(client, "salesmgr@dealflow360.internal")
    resp = client.post(
        "/api/inventory/stock",
        json={"warehouse_id": 1, "product_id": 1, "quantity": 15, "reason": "New Shipment"},
        headers=mgr_headers,
    )
    assert resp.status_code in [200, 201]
    data = resp.json()
    assert data["product_id"] == 1
    assert data["quantity_available"] >= 15


# 5. Restock inventory
def test_05_restock_inventory(client: TestClient):
    mgr_headers = get_auth_headers(client, "salesmgr@dealflow360.internal")
    # Get current inventory record
    inv_list = client.get("/api/inventory?warehouse_id=1&product_id=1", headers=mgr_headers).json()
    assert len(inv_list) > 0
    inv_id = inv_list[0]["id"]
    current_avail = inv_list[0]["quantity_available"]

    resp = client.post(
        f"/api/inventory/restock?inventory_id={inv_id}",
        json={"quantity": 10, "reason": "Restock Batch A"},
        headers=mgr_headers,
    )
    assert resp.status_code == 200
    data = resp.json()
    assert data["quantity_available"] == current_avail + 10


# 6. Restock increments quantity correctly via warehouse product restock endpoint
def test_06_restock_increments_quantity_correctly(client: TestClient):
    mgr_headers = get_auth_headers(client, "salesmgr@dealflow360.internal")
    # Fetch initial summary
    initial_summary = client.get("/api/warehouses/1/inventory/summary", headers=mgr_headers).json()
    prod_entry = next(
        p for c in initial_summary["categories"] for p in c["products"] if p["product_id"] == 1
    )
    initial_qty = prod_entry["quantity_available"]

    # Restock by product
    resp = client.post(
        "/api/warehouses/1/inventory/restock",
        json={"product_id": 1, "quantity": 25, "reason": "Quarterly Restock"},
        headers=mgr_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["quantity_available"] == initial_qty + 25


# 7. No negative inventory
def test_07_no_negative_inventory(client: TestClient):
    admin_headers = get_auth_headers(client, "admin@dealflow360.internal")
    # Attempt adjustment to negative stock
    resp = client.patch(
        "/api/warehouses/1/inventory/1",
        json={"quantity_available": -5},
        headers=admin_headers,
    )
    assert resp.status_code in (400, 422)


# 8. Duplicate warehouse/product inventory handled correctly (upsert)
def test_08_duplicate_warehouse_product_upsert(client: TestClient):
    mgr_headers = get_auth_headers(client, "salesmgr@dealflow360.internal")
    # Add stock twice for same warehouse and product
    resp1 = client.post(
        "/api/inventory/stock",
        json={"warehouse_id": 2, "product_id": 1, "quantity": 5},
        headers=mgr_headers,
    )
    assert resp1.status_code in [200, 201]
    qty1 = resp1.json()["quantity_available"]

    resp2 = client.post(
        "/api/inventory/stock",
        json={"warehouse_id": 2, "product_id": 1, "quantity": 5},
        headers=mgr_headers,
    )
    assert resp2.status_code in [200, 201]
    qty2 = resp2.json()["quantity_available"]
    assert qty2 == qty1 + 5

    # Ensure only 1 record exists in warehouse 2 for product 1
    inv_items = client.get("/api/inventory?warehouse_id=2&product_id=1", headers=mgr_headers).json()
    assert len(inv_items) == 1


# 9. Warehouse inventory grouped by category
def test_09_warehouse_inventory_grouped_by_category(client: TestClient):
    mgr_headers = get_auth_headers(client, "salesmgr@dealflow360.internal")
    resp = client.get("/api/warehouses/1/inventory/summary", headers=mgr_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "categories" in data
    assert len(data["categories"]) >= 1
    for cat in data["categories"]:
        assert "category_name" in cat
        assert "total_units" in cat
        assert "products" in cat
        assert isinstance(cat["products"], list)


# 10. Category totals calculated correctly from real product inventory
def test_10_category_totals_calculated_correctly(client: TestClient):
    mgr_headers = get_auth_headers(client, "salesmgr@dealflow360.internal")
    resp = client.get("/api/warehouses/1/inventory/summary", headers=mgr_headers)
    assert resp.status_code == 200
    data = resp.json()
    for cat in data["categories"]:
        expected_cat_total = sum(p["quantity_available"] for p in cat["products"])
        assert cat["total_units"] == expected_cat_total


# 11. Digital product does not require physical inventory
def test_11_digital_product_no_physical_inventory(client: TestClient):
    admin_headers = get_auth_headers(client, "admin@dealflow360.internal")
    ops_headers = get_auth_headers(client, "ops@dealflow360.internal")
    cust_headers = get_auth_headers(client, "customer@acmecorp.com")
    rep_headers = get_auth_headers(client, "salesrep@dealflow360.internal")

    # Create DIGITAL product
    p_resp = client.post(
        "/api/products",
        json={
            "name": "Cloud DB Key",
            "sku": "SW-CDB-01",
            "unit_price": 500.0,
            "cost_price": 200.0,
            "allowed_discount_percent": 10.0,
            "fulfillment_type": "DIGITAL",
            "is_active": True,
        },
        headers=admin_headers,
    )
    assert p_resp.status_code == 201
    prod_id = p_resp.json()["id"]

    # Customer ID
    cust_id = client.get("/api/portal/profile", headers=cust_headers).json()["id"]

    # Quote DIGITAL product
    q_resp = client.post(
        "/api/quotes",
        json={"customer_id": cust_id, "lines": [{"product_id": prod_id, "quantity": 2, "unit_price": 500.0, "discount_percent": 0.0, "line_type": "ONE_TIME"}]},
        headers=rep_headers,
    )
    assert q_resp.status_code == 201
    quote_id = q_resp.json()["id"]

    # Send & Approve
    client.post(f"/api/quotes/{quote_id}/send", headers=rep_headers)
    client.post(f"/api/approvals/{quote_id}/approve", headers=admin_headers)

    # Customer accepts
    accept_resp = client.post(f"/api/portal/quotes/{quote_id}/confirm", headers=cust_headers)
    assert accept_resp.status_code == 200
    order_id = accept_resp.json()["order_id"]

    # Suggestion for digital product order has 0 warehouse requirements
    sug_resp = client.get(f"/api/orders/{order_id}/fulfillment/suggest", headers=ops_headers)
    assert sug_resp.status_code == 200
    assert len(sug_resp.json()["lines"]) == 0


# 12. Service product does not require physical inventory
def test_12_service_product_no_physical_inventory(client: TestClient):
    admin_headers = get_auth_headers(client, "admin@dealflow360.internal")
    ops_headers = get_auth_headers(client, "ops@dealflow360.internal")
    cust_headers = get_auth_headers(client, "customer@acmecorp.com")
    rep_headers = get_auth_headers(client, "salesrep@dealflow360.internal")

    # Create SERVICE product
    p_resp = client.post(
        "/api/products",
        json={
            "name": "Consulting Block",
            "sku": "SRV-CNS-01",
            "unit_price": 1000.0,
            "cost_price": 500.0,
            "allowed_discount_percent": 5.0,
            "fulfillment_type": "SERVICE",
            "is_active": True,
        },
        headers=admin_headers,
    )
    assert p_resp.status_code == 201
    prod_id = p_resp.json()["id"]

    cust_id = client.get("/api/portal/profile", headers=cust_headers).json()["id"]

    q_resp = client.post(
        "/api/quotes",
        json={"customer_id": cust_id, "lines": [{"product_id": prod_id, "quantity": 1, "unit_price": 1000.0, "discount_percent": 0.0, "line_type": "ONE_TIME"}]},
        headers=rep_headers,
    )
    quote_id = q_resp.json()["id"]
    client.post(f"/api/quotes/{quote_id}/send", headers=rep_headers)
    client.post(f"/api/approvals/{quote_id}/approve", headers=admin_headers)

    accept_resp = client.post(f"/api/portal/quotes/{quote_id}/confirm", headers=cust_headers)
    order_id = accept_resp.json()["order_id"]

    sug_resp = client.get(f"/api/orders/{order_id}/fulfillment/suggest", headers=ops_headers)
    assert sug_resp.status_code == 200
    assert len(sug_resp.json()["lines"]) == 0


# 13. Fulfillment deducts inventory
def test_13_fulfillment_deducts_inventory(client: TestClient):
    ops_headers = get_auth_headers(client, "ops@dealflow360.internal")
    mgr_headers = get_auth_headers(client, "salesmgr@dealflow360.internal")
    admin_headers = get_auth_headers(client, "admin@dealflow360.internal")
    cust_headers = get_auth_headers(client, "customer@acmecorp.com")
    rep_headers = get_auth_headers(client, "salesrep@dealflow360.internal")

    # Create new physical product
    p_resp = client.post(
        "/api/products",
        json={
            "name": "Hardware Terminal",
            "sku": "HW-TERM-99",
            "unit_price": 800.0,
            "cost_price": 400.0,
            "allowed_discount_percent": 10.0,
            "fulfillment_type": "PHYSICAL",
            "is_active": True,
        },
        headers=admin_headers,
    )
    prod_id = p_resp.json()["id"]

    # Stock 10 units in Warehouse 1
    client.post(
        "/api/inventory/stock",
        json={"warehouse_id": 1, "product_id": prod_id, "quantity": 10},
        headers=mgr_headers,
    )

    # Order 2 units
    cust_id = client.get("/api/portal/profile", headers=cust_headers).json()["id"]
    q_resp = client.post(
        "/api/quotes",
        json={"customer_id": cust_id, "lines": [{"product_id": prod_id, "quantity": 2, "unit_price": 800.0, "discount_percent": 0.0, "line_type": "ONE_TIME"}]},
        headers=rep_headers,
    )
    quote_id = q_resp.json()["id"]
    client.post(f"/api/quotes/{quote_id}/send", headers=rep_headers)
    client.post(f"/api/approvals/{quote_id}/approve", headers=admin_headers)

    # Accept quote (which automatically allocates or is confirmed)
    accept_resp = client.post(f"/api/portal/quotes/{quote_id}/confirm", headers=cust_headers)
    order_id = accept_resp.json()["order_id"]

    # Check stock after allocation: 10 - 2 = 8 available, 2 allocated
    inv = client.get(f"/api/inventory?warehouse_id=1&product_id={prod_id}", headers=ops_headers).json()[0]
    assert inv["quantity_available"] == 8
    assert inv["quantity_allocated"] == 2


# 14. Duplicate fulfillment does not double-deduct
def test_14_duplicate_fulfillment_does_not_double_deduct(client: TestClient):
    ops_headers = get_auth_headers(client, "ops@dealflow360.internal")
    mgr_headers = get_auth_headers(client, "salesmgr@dealflow360.internal")
    admin_headers = get_auth_headers(client, "admin@dealflow360.internal")
    cust_headers = get_auth_headers(client, "customer@acmecorp.com")
    rep_headers = get_auth_headers(client, "salesrep@dealflow360.internal")

    p_resp = client.post(
        "/api/products",
        json={
            "name": "Robotic Arm",
            "sku": "HW-ROB-01",
            "unit_price": 3000.0,
            "cost_price": 1800.0,
            "allowed_discount_percent": 10.0,
            "fulfillment_type": "PHYSICAL",
            "is_active": True,
        },
        headers=admin_headers,
    )
    prod_id = p_resp.json()["id"]

    client.post(
        "/api/inventory/stock",
        json={"warehouse_id": 1, "product_id": prod_id, "quantity": 5},
        headers=mgr_headers,
    )

    cust_id = client.get("/api/portal/profile", headers=cust_headers).json()["id"]
    q_resp = client.post(
        "/api/quotes",
        json={"customer_id": cust_id, "lines": [{"product_id": prod_id, "quantity": 1, "unit_price": 3000.0, "discount_percent": 0.0, "line_type": "ONE_TIME"}]},
        headers=rep_headers,
    )
    quote_id = q_resp.json()["id"]
    client.post(f"/api/quotes/{quote_id}/send", headers=rep_headers)
    client.post(f"/api/approvals/{quote_id}/approve", headers=admin_headers)

    accept_resp = client.post(f"/api/portal/quotes/{quote_id}/confirm", headers=cust_headers)
    order_id = accept_resp.json()["order_id"]

    inv_after_accept = client.get(f"/api/inventory?warehouse_id=1&product_id={prod_id}", headers=ops_headers).json()[0]
    avail_after_accept = inv_after_accept["quantity_available"]

    # Re-call confirm fulfillment
    client.post(f"/api/orders/{order_id}/fulfillment/confirm", headers=ops_headers)

    inv_after_reconfirm = client.get(f"/api/inventory?warehouse_id=1&product_id={prod_id}", headers=ops_headers).json()[0]
    assert inv_after_reconfirm["quantity_available"] == avail_after_accept


# 15. Backorder calculated correctly
def test_15_backorder_calculated_correctly(client: TestClient):
    ops_headers = get_auth_headers(client, "ops@dealflow360.internal")
    mgr_headers = get_auth_headers(client, "salesmgr@dealflow360.internal")
    admin_headers = get_auth_headers(client, "admin@dealflow360.internal")
    cust_headers = get_auth_headers(client, "customer@acmecorp.com")
    rep_headers = get_auth_headers(client, "salesrep@dealflow360.internal")

    p_resp = client.post(
        "/api/products",
        json={
            "name": "Rare Sensor",
            "sku": "HW-SENS-RARE",
            "unit_price": 200.0,
            "cost_price": 100.0,
            "allowed_discount_percent": 5.0,
            "fulfillment_type": "PHYSICAL",
            "is_active": True,
        },
        headers=admin_headers,
    )
    prod_id = p_resp.json()["id"]

    # Stock only 2 units
    client.post(
        "/api/inventory/stock",
        json={"warehouse_id": 1, "product_id": prod_id, "quantity": 2},
        headers=mgr_headers,
    )

    # Order 5 units (3 backordered)
    cust_id = client.get("/api/portal/profile", headers=cust_headers).json()["id"]
    q_resp = client.post(
        "/api/quotes",
        json={"customer_id": cust_id, "lines": [{"product_id": prod_id, "quantity": 5, "unit_price": 200.0, "discount_percent": 0.0, "line_type": "ONE_TIME"}]},
        headers=rep_headers,
    )
    quote_id = q_resp.json()["id"]
    client.post(f"/api/quotes/{quote_id}/send", headers=rep_headers)
    client.post(f"/api/approvals/{quote_id}/approve", headers=admin_headers)

    accept_resp = client.post(f"/api/portal/quotes/{quote_id}/confirm", headers=cust_headers)
    order_id = accept_resp.json()["order_id"]

    # Check order detail via portal
    portal_order = client.get(f"/api/portal/orders/{order_id}", headers=cust_headers).json()
    line = portal_order["lines"][0]
    allocated = sum(s["quantity_allocated"] for s in line["fulfillment_splits"])
    backordered = line["quantity"] - allocated
    assert allocated == 2
    assert backordered == 3


# 16. Customer cannot access internal warehouse APIs
def test_16_customer_cannot_access_internal_warehouse_apis(client: TestClient):
    cust_headers = get_auth_headers(client, "customer@acmecorp.com")
    assert client.get("/api/warehouses", headers=cust_headers).status_code == 403
    assert client.get("/api/warehouses/1", headers=cust_headers).status_code == 403
    assert client.get("/api/inventory", headers=cust_headers).status_code == 403
    assert client.get("/api/inventory/low-stock", headers=cust_headers).status_code == 403


# 17. Sales Rep cannot modify inventory
def test_17_sales_rep_cannot_modify_inventory(client: TestClient):
    rep_headers = get_auth_headers(client, "salesrep@dealflow360.internal")
    resp_stock = client.post(
        "/api/inventory/stock",
        json={"warehouse_id": 1, "product_id": 1, "quantity": 10},
        headers=rep_headers,
    )
    assert resp_stock.status_code == 403

    resp_restock = client.post(
        "/api/warehouses/1/inventory/restock",
        json={"product_id": 1, "quantity": 10},
        headers=rep_headers,
    )
    assert resp_restock.status_code == 403


# 18. Audit log created for restock
def test_18_audit_log_created_for_restock(client: TestClient, db_session: Session):
    mgr_headers = get_auth_headers(client, "salesmgr@dealflow360.internal")
    from app.models.audit import AuditLog

    resp = client.post(
        "/api/warehouses/1/inventory/restock",
        json={"product_id": 1, "quantity": 12, "reason": "Audit verification restock"},
        headers=mgr_headers,
    )
    assert resp.status_code == 200

    log = (
        db_session.query(AuditLog)
        .filter(AuditLog.action == "INVENTORY_RESTOCKED")
        .order_by(AuditLog.id.desc())
        .first()
    )
    assert log is not None
    assert "12" in log.new_value


# 19. Warehouse deactivation
def test_19_warehouse_deactivation(client: TestClient):
    mgr_headers = get_auth_headers(client, "salesmgr@dealflow360.internal")
    # Deactivate warehouse 2
    resp = client.post("/api/warehouses/2/deactivate", headers=mgr_headers)
    assert resp.status_code == 200
    assert resp.json()["is_active"] is False

    # Reactivate
    resp_act = client.post("/api/warehouses/2/activate", headers=mgr_headers)
    assert resp_act.status_code == 200
    assert resp_act.json()["is_active"] is True


# 20. Inactive warehouse cannot be used for new allocation
def test_20_inactive_warehouse_cannot_be_allocated(client: TestClient):
    admin_headers = get_auth_headers(client, "admin@dealflow360.internal")
    ops_headers = get_auth_headers(client, "ops@dealflow360.internal")

    # Create warehouse and stock it, then deactivate it
    wh_resp = client.post(
        "/api/warehouses",
        json={"name": "Temporary Deactivated WH", "location": "Remote", "is_active": True},
        headers=admin_headers,
    )
    wh_id = wh_resp.json()["id"]

    p_resp = client.post(
        "/api/products",
        json={
            "name": "Deactivated Test Item",
            "sku": "HW-DEACT-01",
            "unit_price": 100.0,
            "cost_price": 50.0,
            "allowed_discount_percent": 10.0,
            "fulfillment_type": "PHYSICAL",
            "is_active": True,
        },
        headers=admin_headers,
    )
    prod_id = p_resp.json()["id"]

    client.post(
        "/api/inventory/stock",
        json={"warehouse_id": wh_id, "product_id": prod_id, "quantity": 10},
        headers=admin_headers,
    )

    # Now deactivate the warehouse
    client.post(f"/api/warehouses/{wh_id}/deactivate", headers=admin_headers)

    # Create quote for this product
    cust_headers = get_auth_headers(client, "customer@acmecorp.com")
    rep_headers = get_auth_headers(client, "salesrep@dealflow360.internal")
    cust_id = client.get("/api/portal/profile", headers=cust_headers).json()["id"]

    q_resp = client.post(
        "/api/quotes",
        json={"customer_id": cust_id, "lines": [{"product_id": prod_id, "quantity": 2, "unit_price": 100.0, "discount_percent": 0.0, "line_type": "ONE_TIME"}]},
        headers=rep_headers,
    )
    quote_id = q_resp.json()["id"]
    client.post(f"/api/quotes/{quote_id}/send", headers=rep_headers)
    client.post(f"/api/approvals/{quote_id}/approve", headers=admin_headers)

    accept_resp = client.post(f"/api/portal/quotes/{quote_id}/confirm", headers=cust_headers)
    order_id = accept_resp.json()["order_id"]

    # Inactive warehouse should NOT be allocated in suggest
    sug_resp = client.get(f"/api/orders/{order_id}/fulfillment/suggest", headers=ops_headers)
    assert sug_resp.status_code == 200
    for line in sug_resp.json()["lines"]:
        for alloc in line["allocations"]:
            assert alloc["warehouse_id"] != wh_id
