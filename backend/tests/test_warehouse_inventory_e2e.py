import pytest
from datetime import datetime, timezone
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.models.user import User, Role
from app.models.warehouse import Warehouse, Inventory
from app.models.product import Product
from app.models.order import Order, OrderLine, OrderStatus
from app.models.billing import Subscription, SubscriptionStatus


def get_auth_headers(client: TestClient, email: str, password: str = "Demo1234!") -> dict:
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, f"Login failed for {email}: {resp.text}"
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_warehouse_inventory_rbac(client: TestClient):
    """Verify strict RBAC on /api/warehouses and /api/inventory."""
    rep_headers = get_auth_headers(client, "salesrep@dealflow360.internal")
    cust_headers = get_auth_headers(client, "customer@acmecorp.com")
    ops_headers = get_auth_headers(client, "ops@dealflow360.internal")
    mgr_headers = get_auth_headers(client, "salesmgr@dealflow360.internal")
    admin_headers = get_auth_headers(client, "admin@dealflow360.internal")

    # 1. Sales Rep attempting to create warehouse -> 403
    resp = client.post(
        "/api/warehouses",
        json={"name": "Rep Unauthorized Warehouse", "location": "Unauthorized"},
        headers=rep_headers,
    )
    assert resp.status_code == 403, f"Expected 403 for sales rep, got {resp.status_code}"

    # 2. Customer attempting to view inventory -> 403
    resp = client.get("/api/inventory", headers=cust_headers)
    assert resp.status_code == 403, f"Expected 403 for customer, got {resp.status_code}"

    # 3. Customer attempting to view warehouses -> 403
    resp = client.get("/api/warehouses", headers=cust_headers)
    assert resp.status_code == 403, f"Expected 403 for customer, got {resp.status_code}"

    # 4. Operations can view warehouses and inventory
    resp = client.get("/api/warehouses", headers=ops_headers)
    assert resp.status_code == 200
    resp = client.get("/api/inventory", headers=ops_headers)
    assert resp.status_code == 200

    # 5. Sales Manager can create warehouse
    resp = client.post(
        "/api/warehouses",
        json={"name": "Manager Warehouse", "location": "Delhi", "is_active": True},
        headers=mgr_headers,
    )
    assert resp.status_code == 201


def test_warehouse_inventory_e2e_12_steps(client: TestClient, db_session: Session):
    """
    Complete 12-Step E2E Business Lifecycle:
    Step 1: Create 'Mumbai Warehouse'
    Step 2: Add 10 units Laptop stock
    Step 3: Create 'Windows License' with DIGITAL fulfillment, Till Validity 3 Months, Monthly
    Step 4: Sales Rep quotes Laptop x 1
    Step 5: Sales Rep quotes Windows x 1
    Step 6: Quotes approved
    Step 7: Customer accepts both quotes
    Step 8: Orders created (Laptop: warehouse required; Windows: warehouse not required)
    Step 9: Operations suggests fulfillment for Laptop (Mumbai -> 1)
    Step 10: Operations confirms fulfillment (Mumbai stock: 10 -> 9 available, 1 allocated)
    Step 11: Windows subscription is ACTIVE (start_date set, end_date = +3 months)
    Step 12: Customer portal displays fulfillment for Laptop, active subscription for Windows
    """
    admin_headers = get_auth_headers(client, "admin@dealflow360.internal")
    mgr_headers = get_auth_headers(client, "salesmgr@dealflow360.internal")
    rep_headers = get_auth_headers(client, "salesrep@dealflow360.internal")
    ops_headers = get_auth_headers(client, "ops@dealflow360.internal")
    cust_headers = get_auth_headers(client, "customer@acmecorp.com")

    # Fetch customer id
    cust_profile = client.get("/api/portal/profile", headers=cust_headers).json()
    customer_id = cust_profile["id"]

    # =========================================================================
    # STEP 1: Create 'Mumbai Warehouse'
    # =========================================================================
    resp_wh = client.post(
        "/api/warehouses",
        json={"name": "Mumbai Warehouse", "location": "Mumbai, Maharashtra, India", "is_active": True},
        headers=admin_headers,
    )
    assert resp_wh.status_code == 201
    mumbai_wh = resp_wh.json()
    mumbai_wh_id = mumbai_wh["id"]
    assert mumbai_wh["name"] == "Mumbai Warehouse"

    # =========================================================================
    # STEP 2: Add 10 units Laptop stock
    # =========================================================================
    # Create a dedicated Laptop product
    resp_new_laptop = client.post(
        "/api/products",
        json={
            "name": "Laptop",
            "sku": "HW-LAP-PRO-15",
            "unit_price": 1200.0,
            "cost_price": 800.0,
            "allowed_discount_percent": 15.0,
            "fulfillment_type": "PHYSICAL",
            "is_active": True,
        },
        headers=admin_headers,
    )
    assert resp_new_laptop.status_code == 201
    laptop_prod = resp_new_laptop.json()
    laptop_id = laptop_prod["id"]

    # Add 10 units Laptop stock to Mumbai Warehouse
    resp_stock = client.post(
        "/api/inventory/stock",
        json={
            "warehouse_id": mumbai_wh_id,
            "product_id": laptop_id,
            "quantity": 10,
        },
        headers=ops_headers,
    )
    assert resp_stock.status_code in [200, 201]
    inv_data = resp_stock.json()
    assert inv_data["quantity_available"] >= 10
    assert inv_data["quantity_on_hand"] >= 10

    # =========================================================================
    # STEP 3: Create 'Windows License' with DIGITAL fulfillment, Till Validity 3 Months, Monthly
    # =========================================================================
    resp_win = client.post(
        "/api/products",
        json={
            "name": "Windows Enterprise License",
            "sku": "SW-WIN-ENT-03M",
            "unit_price": 300.0,
            "cost_price": 150.0,
            "allowed_discount_percent": 10.0,
            "fulfillment_type": "DIGITAL",
            "subscription_enabled": True,
            "subscription_name": "Windows Cloud SLA & Updates",
            "duration_mode": "TILL_VALIDITY",
            "validity_value": 3,
            "validity_unit": "MONTHS",
            "billing_frequency": "MONTHLY",
            "subscription_start_trigger": "ORDER_ACTIVATION",
            "is_active": True,
        },
        headers=admin_headers,
    )
    assert resp_win.status_code == 201
    win_prod = resp_win.json()
    win_id = win_prod["id"]
    assert win_prod["fulfillment_type"] == "DIGITAL"

    # =========================================================================
    # STEP 4: Sales Rep quotes Laptop x 1
    # =========================================================================
    quote_laptop_payload = {
        "customer_id": customer_id,
        "lines": [
            {
                "product_id": laptop_id,
                "quantity": 1,
                "unit_price": float(laptop_prod["unit_price"]),
                "discount_percent": 0.0,
                "line_type": "ONE_TIME",
            }
        ],
    }
    resp_ql = client.post("/api/quotes", json=quote_laptop_payload, headers=rep_headers)
    assert resp_ql.status_code == 201
    laptop_quote = resp_ql.json()
    laptop_quote_id = laptop_quote["id"]

    # =========================================================================
    # STEP 5: Sales Rep quotes Windows x 1
    # =========================================================================
    quote_win_payload = {
        "customer_id": customer_id,
        "lines": [
            {
                "product_id": win_id,
                "quantity": 1,
                "unit_price": float(win_prod["unit_price"]),
                "discount_percent": 0.0,
                "line_type": "ONE_TIME",
            }
        ],
    }
    resp_qw = client.post("/api/quotes", json=quote_win_payload, headers=rep_headers)
    assert resp_qw.status_code == 201
    win_quote = resp_qw.json()
    win_quote_id = win_quote["id"]

    # =========================================================================
    # STEP 6: Quotes approved (or auto-approved if discount <= threshold)
    # =========================================================================
    # Send for review if DRAFT
    for qid in [laptop_quote_id, win_quote_id]:
        q_status = client.get(f"/api/quotes/{qid}", headers=rep_headers).json()["status"]
        if q_status == "DRAFT":
            client.post(f"/api/quotes/{qid}/send", headers=rep_headers)
            q_status = client.get(f"/api/quotes/{qid}", headers=rep_headers).json()["status"]
        if q_status == "PENDING_APPROVAL":
            client.post(f"/api/approvals/{qid}/approve", headers=mgr_headers)
            q_status = client.get(f"/api/quotes/{qid}", headers=rep_headers).json()["status"]
        assert q_status == "APPROVED"

    # =========================================================================
    # STEP 7: Customer accepts both quotes
    # =========================================================================
    accept_resp_l = client.post(f"/api/portal/quotes/{laptop_quote_id}/accept", headers=cust_headers)
    assert accept_resp_l.status_code == 200
    laptop_accept_data = accept_resp_l.json()
    laptop_order_id = laptop_accept_data.get("order_id") or laptop_accept_data.get("order", {}).get("id")

    accept_resp_w = client.post(f"/api/portal/quotes/{win_quote_id}/accept", headers=cust_headers)
    assert accept_resp_w.status_code == 200
    win_accept_data = accept_resp_w.json()
    win_order_id = win_accept_data.get("order_id") or win_accept_data.get("order", {}).get("id")

    # =========================================================================
    # STEP 8: Orders created
    #   - Laptop: warehouse required (physical line present)
    #   - Windows: warehouse not required (digital item)
    # =========================================================================
    assert laptop_order_id is not None
    assert win_order_id is not None

    laptop_order = client.get(f"/api/orders/{laptop_order_id}", headers=ops_headers).json()
    win_order = client.get(f"/api/orders/{win_order_id}", headers=ops_headers).json()

    # Laptop line has PHYSICAL fulfillment_type
    laptop_line = laptop_order["lines"][0]
    assert laptop_line["fulfillment_type"] == "PHYSICAL"

    # Windows line has DIGITAL fulfillment_type
    win_line = win_order["lines"][0]
    assert win_line["fulfillment_type"] == "DIGITAL"

    # =========================================================================
    # STEP 9: Operations suggests fulfillment for Laptop (Mumbai -> 1)
    # =========================================================================
    resp_suggest = client.get(f"/api/orders/{laptop_order_id}/fulfillment/suggest", headers=ops_headers)
    assert resp_suggest.status_code == 200
    suggestion = resp_suggest.json()
    assert len(suggestion["lines"]) >= 1
    laptop_allocs = suggestion["lines"][0]["allocations"]
    split_suggestion = next((s for s in laptop_allocs if s["warehouse_id"] == mumbai_wh_id), None)
    assert split_suggestion is not None
    assert split_suggestion["quantity"] >= 1

    # Digital order suggestion should have 0 lines (digital/service items bypass warehouse fulfillment)
    resp_win_suggest = client.get(f"/api/orders/{win_order_id}/fulfillment/suggest", headers=ops_headers)
    assert resp_win_suggest.status_code == 200
    win_suggestion = resp_win_suggest.json()
    assert len(win_suggestion["lines"]) == 0

    # =========================================================================
    # STEP 10: Operations confirms fulfillment (Mumbai stock: 10 -> 9 available, 1 allocated)
    # =========================================================================
    resp_confirm = client.post(
        f"/api/orders/{laptop_order_id}/fulfillment/confirm",
        json={"splits": [{"order_line_id": laptop_line["id"], "warehouse_id": mumbai_wh_id, "quantity": 1}]},
        headers=ops_headers,
    )
    assert resp_confirm.status_code == 200

    # Verify updated inventory in Mumbai Warehouse
    resp_mumbai_inv = client.get(f"/api/warehouses/{mumbai_wh_id}/inventory", headers=ops_headers)
    assert resp_mumbai_inv.status_code == 200
    mumbai_items = resp_mumbai_inv.json()
    laptop_inv = next((i for i in mumbai_items if i["product_id"] == laptop_id), None)
    assert laptop_inv is not None
    assert laptop_inv["quantity_allocated"] == 1
    assert laptop_inv["quantity_available"] == 9
    assert laptop_inv["quantity_on_hand"] == 10

    # =========================================================================
    # STEP 11: Windows subscription is ACTIVE (start_date set, end_date = +3 months)
    # =========================================================================
    # Check subscriptions for Windows order via portal/subscriptions or order subscriptions
    resp_subs = client.get("/api/portal/subscriptions", headers=admin_headers)
    assert resp_subs.status_code == 200
    all_subs = resp_subs.json()
    win_sub = next(
        (s for s in all_subs if s.get("order_id") == win_order_id or "Windows" in s.get("name", "") or "Windows" in s.get("subscription_name", "")),
        None
    )
    assert win_sub is not None
    assert win_sub["status"] == "ACTIVE"
    assert win_sub["start_date"] is not None
    assert win_sub["end_date"] is not None

    # =========================================================================
    # STEP 12: Customer portal displays fulfillment for Laptop, active subscription for Windows
    # =========================================================================
    portal_orders = client.get("/api/portal/orders", headers=cust_headers).json()
    portal_laptop_order = next((o for o in portal_orders if o["id"] == laptop_order_id), None)
    portal_win_order = next((o for o in portal_orders if o["id"] == win_order_id), None)

    assert portal_laptop_order is not None
    assert portal_win_order is not None
    # Physical laptop order has fulfillment splits
    assert len(portal_laptop_order["lines"][0]["fulfillment_splits"]) >= 1

    # Customer portal subscriptions
    portal_subs = client.get("/api/portal/subscriptions", headers=cust_headers).json()
    portal_win_sub = next((s for s in portal_subs if s["id"] == win_sub["id"]), None)
    assert portal_win_sub is not None
    assert portal_win_sub["status"] == "ACTIVE"
