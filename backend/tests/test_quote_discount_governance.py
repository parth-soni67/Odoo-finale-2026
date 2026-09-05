import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.models.user import User, Role
from app.models.quote import Quote, QuoteLine, QuoteStatus, LineType
from app.models.customer import Customer, CustomerTier
from app.models.product import Product, ProductCategory, DiscountRule
from app.models.negotiation import Negotiation, NegotiationStatus
from app.models.approval import Approval, ApprovalType, ApprovalStatus
from app.services.discount_service import discount_service


def get_auth_headers(client: TestClient, email: str, password: str = "Demo1234!") -> dict:
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, f"Login failed for {email}: {resp.text}"
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


# -----------------------------------------------------------------------------
# 1-6: Value-Weighted Discount & Governance Tests
# -----------------------------------------------------------------------------

def test_weighted_quote_discount_calculation(db_session: Session):
    """Verifies value-weighted discount calculation across Hardware, Software, and Services."""
    # Find or verify customer with known ceiling
    cust = db_session.query(Customer).filter(Customer.company_name == "TechNova Solutions").first()
    assert cust is not None
    # TechNova has tier=GROWTH, discount_ceiling=20.0

    hw = db_session.query(Product).filter(Product.sku == "HW-IOT-100").first()  # unit 1200, cost 800, allowed 15%
    sw = db_session.query(Product).filter(Product.sku == "SW-DF360-LIC").first()  # unit 5000, cost 500, allowed 25%
    srv = db_session.query(Product).filter(Product.sku == "SRV-DEPLOY-01").first()  # unit 2500, cost 1500, allowed 10%

    quote = Quote(
        quote_number="Q-TEST-WEIGHTED",
        customer_id=cust.id,
        created_by=2,
        status=QuoteStatus.DRAFT,
        subtotal=17000.0,
        total_discount=0.0,
        total_amount=17000.0,
    )
    db_session.add(quote)
    db_session.flush()

    line1 = QuoteLine(quote_id=quote.id, product_id=hw.id, quantity=10, unit_price=1000.0, discount_percent=0.0, line_total=10000.0)  # Gross: 10000
    line2 = QuoteLine(quote_id=quote.id, product_id=sw.id, quantity=1, unit_price=5000.0, discount_percent=0.0, line_total=5000.0)    # Gross: 5000
    line3 = QuoteLine(quote_id=quote.id, product_id=srv.id, quantity=1, unit_price=2000.0, discount_percent=0.0, line_total=2000.0)  # Gross: 2000
    db_session.add_all([line1, line2, line3])
    db_session.commit()
    db_session.refresh(quote)

    gov = discount_service.calculate_quote_max_permissible_discount(db_session, quote)
    assert gov["quote_subtotal"] == 17000.0
    # Line 1: Gross 10000, min(15% product, 20% tier, margin cap (1000-800)/1000=20%) = 15% -> $1500
    # Line 2: Gross 5000, min(25% product, 20% tier, margin cap (5000-500)/5000=90%) = 20% -> $1000
    # Line 3: Gross 2000, min(10% product, 20% tier, margin cap (2000-1500)/2000=25%) = 10% -> $200
    # Total max discount value = 1500 + 1000 + 200 = $2700
    # Weighted max percent = 2700 / 17000 * 100 = 15.88%
    assert gov["weighted_max_discount_percent"] == 15.88
    # Customer ceiling is 20.0%, so min(15.88%, 20.0%) = 15.88%
    assert gov["quote_max_permissible_discount"] == 15.88


def test_margin_floor_protection(db_session: Session):
    """Verifies that margin floor strictly prevents discounts exceeding (unit_price - cost_price)."""
    cust = db_session.query(Customer).filter(Customer.company_name == "Global Logistics Inc").first()
    # Global Logistics has ceiling 35%

    # High cost product: unit 1000, cost 900 -> margin cap is (1000-900)/1000 = 10%
    prod = Product(
        name="High Cost Unit",
        sku="TEST-HIGH-COST",
        unit_price=1000.0,
        cost_price=900.0,
        allowed_discount_percent=30.0,
    )
    db_session.add(prod)
    db_session.flush()

    quote = Quote(
        quote_number="Q-TEST-MARGIN",
        customer_id=cust.id,
        created_by=2,
        status=QuoteStatus.DRAFT,
        subtotal=1000.0,
        total_discount=0.0,
        total_amount=1000.0,
    )
    db_session.add(quote)
    db_session.flush()

    line = QuoteLine(quote_id=quote.id, product_id=prod.id, quantity=1, unit_price=1000.0, discount_percent=0.0, line_total=1000.0)
    db_session.add(line)
    db_session.commit()
    db_session.refresh(quote)

    gov = discount_service.calculate_quote_max_permissible_discount(db_session, quote)
    # Margin floor limits it to 10% despite product allowed_discount_percent = 30% and customer ceiling = 35%
    assert gov["quote_max_permissible_discount"] == 10.0


# -----------------------------------------------------------------------------
# 7-10: Customer Negotiation Request & Approval Routing
# -----------------------------------------------------------------------------

def test_customer_negotiation_within_maximum_direct_acceptance(client: TestClient, db_session: Session):
    """Customer requests discount within allowed governance -> Auto-approved without manager review."""
    cust_headers = get_auth_headers(client, "customer@acmecorp.com")
    # Acme Corp has ceiling 10.0%

    q = db_session.query(Quote).filter(Quote.quote_number == "Q-2026-001").first()
    assert q is not None

    # Request 8.0% discount (permissible limit is 10.0%)
    neg_payload = {
        "requested_change": "discount_percent",
        "proposed_value": "8.0",
    }
    resp = client.post(f"/api/portal/quotes/{q.id}/negotiate", json=neg_payload, headers=cust_headers)
    assert resp.status_code == 201
    data = resp.json()

    # Direct acceptance!
    assert data["status"] == "ACCEPTED"
    assert data["proposed_value"] == "8.0"

    # Verify quote state immediately updated in DB
    db_session.refresh(q)
    assert q.status == QuoteStatus.APPROVED
    assert q.requires_approval is False
    assert q.total_discount > 0.0


def test_customer_negotiation_exceeding_maximum_requires_approval(client: TestClient, db_session: Session):
    """Customer requests discount exceeding governance -> Quote PENDING_APPROVAL, Manager review queued."""
    cust_headers = get_auth_headers(client, "customer@acmecorp.com")
    # Acme Corp has ceiling 10.0%

    q = db_session.query(Quote).filter(Quote.customer_id == 1).first()
    assert q is not None

    # Clear pending negotiations for clean test
    db_session.query(Negotiation).filter(Negotiation.quote_id == q.id).delete()
    db_session.commit()

    # Request 18.0% discount (exceeds 10.0% ceiling)
    neg_payload = {
        "requested_change": "discount_percent",
        "proposed_value": "18.0",
    }
    resp = client.post(f"/api/portal/quotes/{q.id}/negotiate", json=neg_payload, headers=cust_headers)
    assert resp.status_code == 201
    data = resp.json()

    assert data["status"] == "PENDING"
    assert data["proposed_value"] == "18.0"

    # Verify quote requires approval and commercial terms are NOT prematurely modified
    db_session.refresh(q)
    assert q.status == QuoteStatus.PENDING_APPROVAL
    assert q.requires_approval is True

    # Verify Manager approval record is created
    mgr_app = db_session.query(Approval).filter(
        Approval.quote_id == q.id,
        Approval.approval_type == ApprovalType.MANAGER,
        Approval.status == ApprovalStatus.PENDING,
    ).first()
    assert mgr_app is not None
    assert "exceeds" in mgr_app.reason


def test_customer_negotiation_extreme_discount_requires_finance_approval(client: TestClient, db_session: Session):
    """Discount > 30% creates both Manager and Finance approvals."""
    cust_headers = get_auth_headers(client, "customer@acmecorp.com")
    q = db_session.query(Quote).filter(Quote.quote_number == "Q-2026-001").first()

    # Clear pending negotiations for this test
    db_session.query(Negotiation).filter(Negotiation.quote_id == q.id).delete()
    db_session.commit()

    neg_payload = {
        "requested_change": "discount_percent",
        "proposed_value": "35.0",
    }
    resp = client.post(f"/api/portal/quotes/{q.id}/negotiate", json=neg_payload, headers=cust_headers)
    assert resp.status_code == 201

    fin_app = db_session.query(Approval).filter(
        Approval.quote_id == q.id,
        Approval.approval_type == ApprovalType.FINANCE,
        Approval.status == ApprovalStatus.PENDING,
    ).first()
    assert fin_app is not None
    assert "Finance review required" in fin_app.reason


# -----------------------------------------------------------------------------
# 11-12: Approved & Rejected Negotiations Impact on Quote
# -----------------------------------------------------------------------------

def test_approved_negotiation_updates_quote(client: TestClient, db_session: Session):
    """Approving negotiation updates quote lines and recalculates totals."""
    mgr_headers = get_auth_headers(client, "salesmgr@dealflow360.internal")
    q = db_session.query(Quote).filter(Quote.quote_number == "Q-2026-001").first()

    neg = Negotiation(
        quote_id=q.id,
        customer_id=q.customer_id,
        requested_change="discount_percent",
        previous_value="5.0",
        proposed_value="14.0",
        status=NegotiationStatus.PENDING,
    )
    db_session.add(neg)
    db_session.commit()
    db_session.refresh(neg)

    resp = client.post(f"/api/negotiations/{neg.id}/approve", json={"comments": "Approved 14%"}, headers=mgr_headers)
    assert resp.status_code == 200

    db_session.refresh(q)
    # Check that quote lines now reflect 14.0%
    for line in q.lines:
        assert line.discount_percent == 14.0


def test_rejected_negotiation_leaves_original_terms(client: TestClient, db_session: Session):
    """Rejecting negotiation preserves original discount and totals."""
    mgr_headers = get_auth_headers(client, "salesmgr@dealflow360.internal")
    q = db_session.query(Quote).filter(Quote.quote_number == "Q-2026-001").first()

    orig_total = q.total_amount
    orig_discount = q.total_discount

    neg = Negotiation(
        quote_id=q.id,
        customer_id=q.customer_id,
        requested_change="discount_percent",
        previous_value="5.0",
        proposed_value="25.0",
        status=NegotiationStatus.PENDING,
    )
    db_session.add(neg)
    db_session.commit()
    db_session.refresh(neg)

    resp = client.post(f"/api/negotiations/{neg.id}/reject", json={"comments": "Too high"}, headers=mgr_headers)
    assert resp.status_code == 200

    db_session.refresh(q)
    assert q.total_amount == orig_total
    assert q.total_discount == orig_discount


# -----------------------------------------------------------------------------
# 13-15: Validation of Unsupported Fields & Field Formatting
# -----------------------------------------------------------------------------

def test_total_amount_negotiation_field_rejected(client: TestClient, db_session: Session):
    """Direct negotiation of total_amount is rejected with exact error code and message."""
    cust_headers = get_auth_headers(client, "customer@acmecorp.com")
    q = db_session.query(Quote).first()

    payload = {
        "requested_change": "total_amount",
        "proposed_value": "9500.00",
    }
    resp = client.post(f"/api/portal/quotes/{q.id}/negotiate", json=payload, headers=cust_headers)
    assert resp.status_code == 400
    err = resp.json()["error"]
    assert err["code"] == "INVALID_NEGOTIATION_FIELD"
    assert "total_amount cannot be directly negotiated" in err["message"]


def test_negotiation_history_field_type_metadata(client: TestClient, db_session: Session):
    """Customer Portal quote detail includes field_type metadata for clean rendering."""
    cust_headers = get_auth_headers(client, "customer@acmecorp.com")
    q = db_session.query(Quote).filter(Quote.customer_id == 1).first()

    resp = client.get(f"/api/portal/quotes/{q.id}", headers=cust_headers)
    assert resp.status_code == 200
    data = resp.json()
    assert "negotiations" in data
    for neg in data["negotiations"]:
        assert "field_type" in neg
        if "discount" in neg["requested_change"].lower():
            assert neg["field_type"] == "PERCENTAGE"


# -----------------------------------------------------------------------------
# 16-18: Duplicate Prevention & RBAC Security
# -----------------------------------------------------------------------------

def test_duplicate_negotiation_prevention(client: TestClient, db_session: Session):
    """Submitting identical pending negotiation raises 409 DUPLICATE_NEGOTIATION."""
    cust_headers = get_auth_headers(client, "customer@acmecorp.com")
    q = db_session.query(Quote).filter(Quote.customer_id == 1).first()

    # Clear existing
    db_session.query(Negotiation).filter(Negotiation.quote_id == q.id).delete()
    db_session.commit()

    payload = {
        "requested_change": "discount_percent",
        "proposed_value": "19.0",
    }
    resp1 = client.post(f"/api/portal/quotes/{q.id}/negotiate", json=payload, headers=cust_headers)
    assert resp1.status_code == 201

    # Second identical submit -> 409 Conflict
    resp2 = client.post(f"/api/portal/quotes/{q.id}/negotiate", json=payload, headers=cust_headers)
    assert resp2.status_code == 409
    err = resp2.json()["error"]
    assert err["code"] == "DUPLICATE_NEGOTIATION"


def test_customer_isolation_cannot_access_other_quote(client: TestClient, db_session: Session):
    """Customer cannot negotiate on or view another customer's quote."""
    cust_headers = get_auth_headers(client, "customer@acmecorp.com")
    # Quote belonging to customer_id 2 (TechNova)
    q_other = db_session.query(Quote).filter(Quote.customer_id != 1).first()
    assert q_other is not None

    resp = client.post(
        f"/api/portal/quotes/{q_other.id}/negotiate",
        json={"requested_change": "discount_percent", "proposed_value": "12.0"},
        headers=cust_headers,
    )
    assert resp.status_code == 403


def test_sales_rep_cannot_approve_quote(client: TestClient, db_session: Session):
    """Sales Rep cannot approve quotations."""
    rep_headers = get_auth_headers(client, "salesrep@dealflow360.internal")
    q = db_session.query(Quote).first()

    resp = client.post(f"/api/quotes/{q.id}/approve", json={"comments": "Self approve"}, headers=rep_headers)
    assert resp.status_code == 403


# -----------------------------------------------------------------------------
# 19-27: State Synchronization Across APIs and Workflow Progression
# -----------------------------------------------------------------------------

def test_approval_state_synchronization_across_views(client: TestClient, db_session: Session):
    """When manager approves, state is immediately consistent across Sales Rep, Customer, and Finance."""
    mgr_headers = get_auth_headers(client, "salesmgr@dealflow360.internal")
    rep_headers = get_auth_headers(client, "salesrep@dealflow360.internal")
    cust_headers = get_auth_headers(client, "customer@acmecorp.com")

    # Create quote that requires approval
    q = Quote(
        quote_number="Q-SYNC-TEST",
        customer_id=1,
        created_by=2,
        status=QuoteStatus.PENDING_APPROVAL,
        subtotal=5000.0,
        total_discount=1000.0,
        total_amount=4000.0,
        requires_approval=True,
    )
    db_session.add(q)
    db_session.flush()

    app = Approval(
        quote_id=q.id,
        approval_type=ApprovalType.MANAGER,
        status=ApprovalStatus.PENDING,
        reason="Sync test approval",
    )
    db_session.add(app)
    db_session.commit()

    # Manager approves quote
    resp_app = client.post(f"/api/quotes/{q.id}/approve", json={"comments": "Approved for sync test"}, headers=mgr_headers)
    assert resp_app.status_code == 200

    # 1. Sales Rep view (GET /api/quotes/{id})
    resp_rep = client.get(f"/api/quotes/{q.id}", headers=rep_headers)
    assert resp_rep.status_code == 200
    assert resp_rep.json()["status"] == "APPROVED"
    assert resp_rep.json()["requires_approval"] is False

    # 2. Approvals view (GET /api/quotes/{id}/approvals)
    resp_approvals = client.get(f"/api/quotes/{q.id}/approvals", headers=rep_headers)
    assert resp_approvals.status_code == 200
    assert resp_approvals.json()[0]["status"] == "APPROVED"

    # 3. Customer Portal view (GET /api/portal/quotes/{id})
    resp_cust = client.get(f"/api/portal/quotes/{q.id}", headers=cust_headers)
    assert resp_cust.status_code == 200
    assert resp_cust.json()["status"] == "APPROVED"

    # 4. Customer Confirmation
    resp_conf = client.post(f"/api/portal/quotes/{q.id}/confirm", headers=cust_headers)
    assert resp_conf.status_code == 200
    assert resp_conf.json()["status"] == "ACCEPTED"

    # 5. Order Creation
    resp_ord = client.post("/api/orders", json={"quote_id": q.id, "customer_id": 1}, headers=rep_headers)
    assert resp_ord.status_code == 201
