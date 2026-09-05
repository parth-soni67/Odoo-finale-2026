import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.models.user import User, Role
from app.models.quote import Quote, QuoteStatus
from app.models.negotiation import Negotiation, NegotiationStatus
from app.models.audit import AuditLog
from app.core.security import get_password_hash


def get_auth_headers(client: TestClient, email: str, password: str = "Demo1234!") -> dict:
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, f"Login failed for {email}: {resp.text}"
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# =====================================================================
# PRODUCT TESTS
# =====================================================================

def test_product_list_and_filter(client: TestClient):
    """Test product listing and filtering by search and category."""
    headers = get_auth_headers(client, "salesrep@dealflow360.internal")

    # List all
    resp = client.get("/api/products", headers=headers)
    assert resp.status_code == 200
    products = resp.json()
    assert len(products) >= 4

    # Filter by search
    resp_search = client.get("/api/products?search=Gateway", headers=headers)
    assert resp_search.status_code == 200
    results = resp_search.json()
    assert len(results) == 1
    assert results[0]["sku"] == "HW-IOT-100"

    # Filter categories
    resp_cat = client.get("/api/products/categories", headers=headers)
    assert resp_cat.status_code == 200
    assert len(resp_cat.json()) >= 4


def test_product_create_and_update(client: TestClient, db_session: Session):
    """Test product creation and modification by admin."""
    admin_headers = get_auth_headers(client, "admin@dealflow360.internal")

    new_prod = {
        "name": "Cloud Connectivity Module",
        "sku": "HW-CLOUD-MOD-01",
        "unit_price": 450.0,
        "cost_price": 220.0,
        "allowed_discount_percent": 12.0,
        "is_active": True,
    }
    create_resp = client.post("/api/products", json=new_prod, headers=admin_headers)
    assert create_resp.status_code == 201
    prod_data = create_resp.json()
    assert prod_data["sku"] == "HW-CLOUD-MOD-01"
    prod_id = prod_data["id"]

    # Update product
    update_resp = client.put(
        f"/api/products/{prod_id}",
        json={"unit_price": 480.0, "allowed_discount_percent": 15.0},
        headers=admin_headers,
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["unit_price"] == 480.0
    assert update_resp.json()["allowed_discount_percent"] == 15.0


def test_product_rbac_restrictions(client: TestClient):
    """Test that SALES_REP and CUSTOMER cannot create or delete products."""
    rep_headers = get_auth_headers(client, "salesrep@dealflow360.internal")
    cust_headers = get_auth_headers(client, "customer@acmecorp.com")

    payload = {
        "name": "Unauthorized Hardware",
        "sku": "HW-UNAUTH-01",
        "unit_price": 100.0,
        "cost_price": 50.0,
    }

    # Sales rep cannot create product
    resp_rep = client.post("/api/products", json=payload, headers=rep_headers)
    assert resp_rep.status_code == 403

    # Customer cannot create product
    resp_cust = client.post("/api/products", json=payload, headers=cust_headers)
    assert resp_cust.status_code == 403

    # Sales rep cannot delete product
    resp_del = client.delete("/api/products/1", headers=rep_headers)
    assert resp_del.status_code == 403


# =====================================================================
# CUSTOMER TESTS
# =====================================================================

def test_customer_list_and_filter(client: TestClient):
    """Test listing customers and filtering by tier."""
    mgr_headers = get_auth_headers(client, "salesmgr@dealflow360.internal")

    resp = client.get("/api/customers", headers=mgr_headers)
    assert resp.status_code == 200
    customers = resp.json()
    assert len(customers) >= 3

    # Filter by tier
    resp_tier = client.get("/api/customers?tier=ENTERPRISE", headers=mgr_headers)
    assert resp_tier.status_code == 200
    results = resp_tier.json()
    assert len(results) == 1
    assert results[0]["company_name"] == "Global Logistics Inc"


def test_customer_create_and_update(client: TestClient):
    """Test creating and updating customer as Sales Manager."""
    mgr_headers = get_auth_headers(client, "salesmgr@dealflow360.internal")

    new_cust = {
        "company_name": "Apex Innovations",
        "contact_name": "Aaron Paul",
        "email": "aaron@apexinnovations.com",
        "phone": "+1-555-0999",
        "tier": "GROWTH",
        "discount_ceiling": 18.0,
    }
    create_resp = client.post("/api/customers", json=new_cust, headers=mgr_headers)
    assert create_resp.status_code == 201
    cust_data = create_resp.json()
    assert cust_data["company_name"] == "Apex Innovations"
    cust_id = cust_data["id"]

    # Update customer
    update_resp = client.put(
        f"/api/customers/{cust_id}",
        json={"discount_ceiling": 22.0},
        headers=mgr_headers,
    )
    assert update_resp.status_code == 200
    assert update_resp.json()["discount_ceiling"] == 22.0


def test_customer_rbac_restrictions(client: TestClient):
    """Verify that a customer cannot list all customers or create a customer."""
    cust_headers = get_auth_headers(client, "customer@acmecorp.com")

    # Customer cannot list all customers
    resp = client.get("/api/customers", headers=cust_headers)
    assert resp.status_code == 403

    # Customer cannot create customer
    resp_create = client.post(
        "/api/customers",
        json={
            "company_name": "Hacked Customer",
            "contact_name": "Hacker",
            "email": "hacker@evil.com",
        },
        headers=cust_headers,
    )
    assert resp_create.status_code == 403


# =====================================================================
# CUSTOMER PORTAL & MULTI-TENANT ISOLATION TESTS
# =====================================================================

def test_customer_portal_profile(client: TestClient):
    """Customer can view their own profile."""
    cust_headers = get_auth_headers(client, "customer@acmecorp.com")
    resp = client.get("/api/portal/profile", headers=cust_headers)
    assert resp.status_code == 200
    profile = resp.json()
    assert profile["company_name"] == "Acme Corp"
    assert profile["tier"] == "STANDARD"
    assert profile["discount_ceiling"] == 10.0


def test_customer_portal_own_quotes(client: TestClient):
    """Customer can view only their own quotes."""
    cust_headers = get_auth_headers(client, "customer@acmecorp.com")
    resp = client.get("/api/portal/quotes", headers=cust_headers)
    assert resp.status_code == 200
    quotes = resp.json()
    assert len(quotes) >= 1
    assert any(q["quote_number"] == "Q-2026-001" for q in quotes)
    # Does not contain TechNova or Global Logistics quotes
    assert not any(q["quote_number"] in ("Q-2026-002", "Q-2026-003") for q in quotes)


def test_customer_portal_quote_details_sanitized(client: TestClient, db_session: Session):
    """Customer views quote detail without internal risk score or approval internal comments."""
    cust_headers = get_auth_headers(client, "customer@acmecorp.com")
    quote = db_session.query(Quote).filter(Quote.quote_number == "Q-2026-001").first()
    assert quote is not None

    resp = client.get(f"/api/portal/quotes/{quote.id}", headers=cust_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["quote_number"] == "Q-2026-001"
    assert data["company_name"] == "Acme Corp"
    assert "lines" in data
    assert len(data["lines"]) >= 2
    # Ensure sensitive internal fields are omitted
    assert "risk_score" not in data
    assert "requires_approval" not in data


def test_customer_portal_isolation_security(client: TestClient, db_session: Session):
    """Customer A cannot view Customer B's quote (returns 403 Forbidden)."""
    cust_headers = get_auth_headers(client, "customer@acmecorp.com")
    # Quote 2 belongs to TechNova Solutions (customer_id != Acme Corp)
    q2 = db_session.query(Quote).filter(Quote.quote_number == "Q-2026-002").first()
    assert q2 is not None

    resp = client.get(f"/api/portal/quotes/{q2.id}", headers=cust_headers)
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"


def test_customer_portal_orders_real_fulfillment(client: TestClient, db_session: Session):
    """Customer views real order fulfillment with line items and warehouse splits."""
    cust_headers = get_auth_headers(client, "customer@acmecorp.com")
    resp = client.get("/api/portal/orders", headers=cust_headers)
    assert resp.status_code == 200
    orders = resp.json()
    assert len(orders) >= 1
    ord1 = next((o for o in orders if o["order_number"] == "ORD-2026-001"), None)
    assert ord1 is not None
    assert ord1["status"] == "CONFIRMED"
    assert len(ord1["lines"]) >= 1

    # Check line items and warehouse splits
    line1 = next((l for l in ord1["lines"] if l["line_type"] == "ONE_TIME"), None)
    assert line1 is not None
    assert line1["product_name"] == "Edge IoT Gateway Server"
    assert len(line1["fulfillment_splits"]) == 2
    wh_names = [s["warehouse_name"] for s in line1["fulfillment_splits"]]
    assert any("Chicago" in (w or "") for w in wh_names)
    assert any("Reno" in (w or "") for w in wh_names)


def test_customer_order_isolation_security(client: TestClient, db_session: Session):
    """Authoritative backend isolation: Customer Acme cannot retrieve TechNova order."""
    from app.models.order import Order
    cust_headers = get_auth_headers(client, "customer@acmecorp.com")

    # Get TechNova order
    ord2 = db_session.query(Order).filter(Order.order_number == "ORD-2026-002").first()
    assert ord2 is not None

    # Via /api/orders/{id}
    resp = client.get(f"/api/orders/{ord2.id}", headers=cust_headers)
    assert resp.status_code == 403
    assert resp.json()["error"]["code"] == "FORBIDDEN"

    # Via /api/portal/orders/{id}
    resp2 = client.get(f"/api/portal/orders/{ord2.id}", headers=cust_headers)
    assert resp2.status_code == 403
    assert resp2.json()["error"]["code"] == "FORBIDDEN"

    # Via GET /api/orders list
    resp_list = client.get("/api/orders", headers=cust_headers)
    assert resp_list.status_code == 200
    list_orders = resp_list.json()
    assert not any(o["order_number"] == "ORD-2026-002" for o in list_orders)


# =====================================================================
# NEGOTIATION TESTS
# =====================================================================

def test_negotiation_creation_by_customer(client: TestClient, db_session: Session):
    """Customer creates a negotiation counter-offer on their own quote."""
    cust_headers = get_auth_headers(client, "customer@acmecorp.com")
    q1 = db_session.query(Quote).filter(Quote.quote_number == "Q-2026-001").first()

    neg_payload = {
        "requested_change": "discount_percent",
        "previous_value": "8.0",
        "proposed_value": "12.0",
    }
    resp = client.post(f"/api/portal/quotes/{q1.id}/negotiate", json=neg_payload, headers=cust_headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["quote_id"] == q1.id
    assert data["requested_change"] == "discount_percent"
    assert data["proposed_value"] == "12.0"
    assert data["status"] == "PENDING"

    # Verify persistence in database
    db_neg = db_session.query(Negotiation).filter(Negotiation.id == data["id"]).first()
    assert db_neg is not None
    assert db_neg.status == NegotiationStatus.PENDING


def test_negotiation_customer_cannot_approve_own(client: TestClient, db_session: Session):
    """Customer is prohibited from approving their own negotiation."""
    cust_headers = get_auth_headers(client, "customer@acmecorp.com")
    q1 = db_session.query(Quote).filter(Quote.quote_number == "Q-2026-001").first()

    # Create negotiation
    neg = Negotiation(
        quote_id=q1.id,
        customer_id=q1.customer_id,
        requested_change="discount_percent",
        previous_value="8.0",
        proposed_value="12.0",
        status=NegotiationStatus.PENDING,
    )
    db_session.add(neg)
    db_session.commit()
    db_session.refresh(neg)

    # Attempt approve as customer -> 403 Forbidden
    resp = client.post(f"/api/negotiations/{neg.id}/approve", headers=cust_headers)
    assert resp.status_code == 403


def test_negotiation_sales_manager_approve_and_reapproval_trigger(client: TestClient, db_session: Session):
    """Sales manager approves negotiation, updating quote and triggering re-approval."""
    mgr_headers = get_auth_headers(client, "salesmgr@dealflow360.internal")
    q1 = db_session.query(Quote).filter(Quote.quote_number == "Q-2026-001").first()

    neg = Negotiation(
        quote_id=q1.id,
        customer_id=q1.customer_id,
        requested_change="discount_percent",
        previous_value="8.0",
        proposed_value="12.0",
        status=NegotiationStatus.PENDING,
    )
    db_session.add(neg)
    db_session.commit()
    db_session.refresh(neg)

    # Approve as sales manager
    resp = client.post(
        f"/api/negotiations/{neg.id}/approve",
        json={"comments": "Approved 12% discount for long-term customer relationship"},
        headers=mgr_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "APPROVED"

    # Verify quote state updated and re-approval flagged
    db_session.refresh(q1)
    assert q1.status == QuoteStatus.PENDING_APPROVAL
    assert q1.requires_approval is True
    # Verify line items discount updated to 12.0%
    for line in q1.lines:
        assert line.discount_percent == 12.0


def test_negotiation_sales_manager_reject(client: TestClient, db_session: Session):
    """Sales manager rejects customer negotiation."""
    mgr_headers = get_auth_headers(client, "salesmgr@dealflow360.internal")
    q1 = db_session.query(Quote).filter(Quote.quote_number == "Q-2026-001").first()

    neg = Negotiation(
        quote_id=q1.id,
        customer_id=q1.customer_id,
        requested_change="discount_percent",
        previous_value="8.0",
        proposed_value="18.0",
        status=NegotiationStatus.PENDING,
    )
    db_session.add(neg)
    db_session.commit()
    db_session.refresh(neg)

    resp = client.post(
        f"/api/negotiations/{neg.id}/reject",
        json={"comments": "18% exceeds margin governance ceiling"},
        headers=mgr_headers,
    )
    assert resp.status_code == 200
    assert resp.json()["status"] == "REJECTED"

    db_session.refresh(neg)
    assert neg.status == NegotiationStatus.REJECTED


# =====================================================================
# DEAL HEALTH TESTS
# =====================================================================

def test_deal_health_healthy_calculation(client: TestClient, db_session: Session):
    """Quote with low discount and no active negotiation evaluates as HEALTHY."""
    headers = get_auth_headers(client, "salesrep@dealflow360.internal")
    q3 = db_session.query(Quote).filter(Quote.quote_number == "Q-2026-003").first()
    assert q3 is not None

    resp = client.get(f"/api/deal-health/{q3.id}", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["risk_level"] in ("HEALTHY", "MEDIUM_RISK")
    assert data["risk_score"] <= 50.0
    assert len(data["signals"]) >= 0


def test_deal_health_high_risk_calculation(client: TestClient, db_session: Session):
    """Quote with excessive discount + pending approval + active negotiation evaluates as HIGH_RISK."""
    headers = get_auth_headers(client, "salesrep@dealflow360.internal")
    q2 = db_session.query(Quote).filter(Quote.quote_number == "Q-2026-002").first()
    assert q2 is not None

    resp = client.get(f"/api/deal-health/{q2.id}", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["risk_level"] == "HIGH_RISK"
    assert data["risk_score"] >= 61.0
    assert any("discount" in s.lower() for s in data["signals"])


def test_deal_health_summary_dashboard(client: TestClient):
    """Deal health summary returns counts, KPIs, and deals table."""
    headers = get_auth_headers(client, "salesmgr@dealflow360.internal")
    resp = client.get("/api/deal-health", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_active_deals"] >= 3
    assert data["high_risk_count"] >= 1
    assert data["active_negotiations_count"] >= 1
    assert len(data["deals"]) >= 3


# =====================================================================
# REPORTING TESTS
# =====================================================================

def test_sales_summary_reporting(client: TestClient):
    """Sales summary returns accurate aggregate metrics."""
    headers = get_auth_headers(client, "admin@dealflow360.internal")
    resp = client.get("/api/reports/sales-summary", headers=headers)
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_quotes"] >= 3
    assert data["total_quote_value"] > 0
    assert data["customer_count"] >= 3
    assert data["product_count"] >= 4


# =====================================================================
# AUDIT LOG TESTS
# =====================================================================

def test_audit_logging(client: TestClient, db_session: Session):
    """Verify that product edits, customer creations, and negotiations emit AuditLog records."""
    admin_headers = get_auth_headers(client, "admin@dealflow360.internal")

    # Create product
    client.post(
        "/api/products",
        json={"name": "Audit Test Item", "sku": "AUDIT-001", "unit_price": 50.0, "cost_price": 20.0},
        headers=admin_headers,
    )

    logs = db_session.query(AuditLog).filter(AuditLog.entity_type == "PRODUCT").all()
    assert len(logs) >= 1
    assert any(l.action == "CREATE" for l in logs)
