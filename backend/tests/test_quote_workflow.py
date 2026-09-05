"""Automated Test Suite for Quotation Engine, Discount Governance & Approval Workflow.

Validates all 16 required Person 2 scenarios:
1. Create quote
2. Get quote
3. Add multiple quote lines
4. Correct price calculation
5. Correct discount calculation
6. Product-level discount violation
7. Customer ceiling violation
8. Risk score calculation
9. No-approval case
10. Manager approval required
11. Finance approval required
12. Manager approval flow
13. Manager rejection flow
14. Quote status transitions
15. RBAC enforcement
16. Audit log creation
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.models.quote import Quote, QuoteStatus
from app.models.approval import Approval, ApprovalStatus, ApprovalType
from app.models.audit import AuditLog


def get_auth_token(client: TestClient, email: str, password: str = "Demo1234!") -> str:
    """Helper to authenticate and return a bearer access token."""
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, f"Login failed for {email}: {resp.text}"
    return resp.json()["access_token"]


def test_1_create_quote(client: TestClient):
    """Scenario 1: Authenticated Sales Rep creates a new quote."""
    token = get_auth_token(client, "salesrep@dealflow360.internal")
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "customer_id": 1,
        "lines": [
            {
                "product_id": 1,  # Edge IoT Gateway Server ($1200)
                "quantity": 2,
                "unit_price": 1200.0,
                "discount_percent": 5.0,
                "line_type": "ONE_TIME",
            }
        ],
    }

    response = client.post("/api/quotes", json=payload, headers=headers)
    assert response.status_code == 201
    data = response.json()
    assert data["quote_number"].startswith("QT-2026-")
    assert data["customer_id"] == 1
    assert len(data["lines"]) == 1
    assert data["lines"][0]["quantity"] == 2
    assert data["lines"][0]["unit_price"] == 1200.0


def test_2_get_quote(client: TestClient):
    """Scenario 2: Retrieve quote by ID with populated customer and line items."""
    token = get_auth_token(client, "salesrep@dealflow360.internal")
    headers = {"Authorization": f"Bearer {token}"}

    create_resp = client.post(
        "/api/quotes",
        json={"customer_id": 1, "lines": [{"product_id": 1, "quantity": 1, "discount_percent": 0.0}]},
        headers=headers,
    )
    quote_id = create_resp.json()["id"]

    get_resp = client.get(f"/api/quotes/{quote_id}", headers=headers)
    assert get_resp.status_code == 200
    data = get_resp.json()
    assert data["id"] == quote_id
    assert data["customer"]["company_name"] == "Acme Corp"
    assert len(data["lines"]) == 1


def test_3_add_multiple_quote_lines(client: TestClient):
    """Scenario 3: Create a quote with diverse product lines (Hardware + Services)."""
    token = get_auth_token(client, "salesrep@dealflow360.internal")
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "customer_id": 1,
        "lines": [
            {"product_id": 1, "quantity": 10, "discount_percent": 5.0},  # HW ($1200)
            {"product_id": 3, "quantity": 1, "discount_percent": 5.0},   # Service ($2500)
            {"product_id": 4, "quantity": 3, "discount_percent": 0.0},   # SLA ($800)
        ],
    }

    resp = client.post("/api/quotes", json=payload, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert len(data["lines"]) == 3


def test_4_correct_price_calculation(client: TestClient):
    """Scenario 4: Verify gross price calculation: quantity x unit_price across lines."""
    token = get_auth_token(client, "salesrep@dealflow360.internal")
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "customer_id": 1,
        "lines": [
            {"product_id": 1, "quantity": 4, "unit_price": 1200.0, "discount_percent": 0.0},  # 4 * 1200 = 4800
            {"product_id": 3, "quantity": 2, "unit_price": 2500.0, "discount_percent": 0.0},  # 2 * 2500 = 5000
        ],
    }

    resp = client.post("/api/quotes", json=payload, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["subtotal"] == 9800.0
    assert data["total_amount"] == 9800.0
    assert data["total_discount"] == 0.0


def test_5_correct_discount_calculation(client: TestClient):
    """Scenario 5: Verify line discount amount and quote net totals."""
    token = get_auth_token(client, "salesrep@dealflow360.internal")
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "customer_id": 1,
        "lines": [
            # 10 * $1200 = $12,000; 8% discount = $960; line total = $11,040
            {"product_id": 1, "quantity": 10, "unit_price": 1200.0, "discount_percent": 8.0},
        ],
    }

    resp = client.post("/api/quotes", json=payload, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    line = data["lines"][0]
    assert line["discount_amount"] == 960.0
    assert line["line_total"] == 11040.0
    assert data["subtotal"] == 12000.0
    assert data["total_discount"] == 960.0
    assert data["total_amount"] == 11040.0


def test_6_product_level_discount_violation(client: TestClient):
    """Scenario 6: Line-level governance detects violation on Deployment Package (allowed 10%, requested 18%)."""
    token = get_auth_token(client, "salesrep@dealflow360.internal")
    headers = {"Authorization": f"Bearer {token}"}

    # Judge scenario:
    # Edge IoT Gateway: qty 10, discount 8% (allowed 10% -> OK)
    # Deployment Package: qty 1, discount 18% (allowed 10% -> VIOLATION: excess 8%)
    payload = {
        "customer_id": 1,  # Acme Corp (ceiling 10%)
        "lines": [
            {"product_id": 1, "quantity": 10, "unit_price": 1200.0, "discount_percent": 8.0},
            {"product_id": 3, "quantity": 1, "unit_price": 2500.0, "discount_percent": 18.0},
        ],
    }

    resp = client.post("/api/quotes", json=payload, headers=headers)
    assert resp.status_code == 201
    quote = resp.json()
    quote_id = quote["id"]

    # Check risk endpoint
    risk_resp = client.post(f"/api/quotes/{quote_id}/risk", headers=headers)
    assert risk_resp.status_code == 200
    risk_data = risk_resp.json()

    assert risk_data["requires_approval"] is True
    assert len(risk_data["violations"]) == 1
    violation = risk_data["violations"][0]
    assert "Deployment" in violation["product"]
    assert violation["allowed_discount"] == 10.0
    assert violation["requested_discount"] == 18.0
    assert violation["excess"] == 8.0


def test_7_customer_ceiling_violation(client: TestClient):
    """Scenario 7: Quote overall discount exceeds customer ceiling."""
    token = get_auth_token(client, "salesrep@dealflow360.internal")
    headers = {"Authorization": f"Bearer {token}"}

    # Acme Corp discount ceiling is 10.0%. Product 2 allows 25%, but customer tier is Standard (10%).
    # Requesting 20% discount on Software breaches customer ceiling.
    payload = {
        "customer_id": 1,
        "lines": [
            {"product_id": 2, "quantity": 1, "discount_percent": 20.0},
        ],
    }

    resp = client.post("/api/quotes", json=payload, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["requires_approval"] is True
    assert data["risk_score"] > 35.0


def test_8_risk_score_calculation(client: TestClient):
    """Scenario 8: Deterministic risk score matches 72 in judge-friendly scenario."""
    token = get_auth_token(client, "salesrep@dealflow360.internal")
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "customer_id": 1,
        "lines": [
            {"product_id": 1, "quantity": 10, "discount_percent": 8.0},
            {"product_id": 3, "quantity": 1, "discount_percent": 18.0},
        ],
    }

    resp = client.post("/api/quotes", json=payload, headers=headers)
    assert resp.status_code == 201
    quote_data = resp.json()
    # Risk score should be deterministic and equal 72
    assert quote_data["risk_score"] == 72.0


def test_9_no_approval_case(client: TestClient):
    """Scenario 9: Compliant discount requires zero approval and auto-approves."""
    token = get_auth_token(client, "salesrep@dealflow360.internal")
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "customer_id": 1,
        "lines": [
            {"product_id": 1, "quantity": 2, "discount_percent": 5.0},
            {"product_id": 3, "quantity": 1, "discount_percent": 5.0},
        ],
    }

    resp = client.post("/api/quotes", json=payload, headers=headers)
    assert resp.status_code == 201
    data = resp.json()
    assert data["requires_approval"] is False
    assert data["risk_score"] < 35.0
    assert data["status"] == "APPROVED"


def test_10_manager_approval_required(client: TestClient):
    """Scenario 10: Moderate violation routes to Sales Manager."""
    token = get_auth_token(client, "salesrep@dealflow360.internal")
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "customer_id": 1,
        "lines": [
            {"product_id": 1, "quantity": 10, "discount_percent": 8.0},
            {"product_id": 3, "quantity": 1, "discount_percent": 18.0},
        ],
    }

    resp = client.post("/api/quotes", json=payload, headers=headers)
    quote = resp.json()
    assert quote["status"] == "PENDING_APPROVAL"

    # Inspect approvals
    appr_resp = client.get(f"/api/quotes/{quote['id']}/approvals", headers=headers)
    assert appr_resp.status_code == 200
    approvals = appr_resp.json()
    assert len(approvals) == 1
    assert approvals[0]["approval_type"] == "MANAGER"
    assert approvals[0]["status"] == "PENDING"


def test_11_finance_approval_required(client: TestClient):
    """Scenario 11: High-risk deep discount (>30% or below cost) routes to Finance and Manager."""
    token = get_auth_token(client, "salesrep@dealflow360.internal")
    headers = {"Authorization": f"Bearer {token}"}

    payload = {
        "customer_id": 1,
        "lines": [
            # 50% discount on hardware: drops unit price from $1200 to $600 (below cost $800!)
            {"product_id": 1, "quantity": 5, "discount_percent": 50.0},
        ],
    }

    resp = client.post("/api/quotes", json=payload, headers=headers)
    quote = resp.json()
    assert quote["requires_approval"] is True
    assert quote["risk_score"] >= 75.0

    appr_resp = client.get(f"/api/quotes/{quote['id']}/approvals", headers=headers)
    approvals = appr_resp.json()
    types = [a["approval_type"] for a in approvals]
    assert "MANAGER" in types
    assert "FINANCE" in types


def test_12_manager_approval_flow(client: TestClient):
    """Scenario 12: Sales Manager approves quote and it becomes APPROVED."""
    rep_token = get_auth_token(client, "salesrep@dealflow360.internal")
    rep_headers = {"Authorization": f"Bearer {rep_token}"}

    # 1. Create quote needing Manager approval
    create_resp = client.post(
        "/api/quotes",
        json={
            "customer_id": 1,
            "lines": [
                {"product_id": 1, "quantity": 10, "discount_percent": 8.0},
                {"product_id": 3, "quantity": 1, "discount_percent": 18.0},
            ],
        },
        headers=rep_headers,
    )
    quote_id = create_resp.json()["id"]

    # 2. Login as Sales Manager
    mgr_token = get_auth_token(client, "salesmgr@dealflow360.internal")
    mgr_headers = {"Authorization": f"Bearer {mgr_token}"}

    # 3. Check pending approvals list
    pending_resp = client.get("/api/approvals/pending", headers=mgr_headers)
    assert pending_resp.status_code == 200
    pending_ids = [p["quote_id"] for p in pending_resp.json()]
    assert quote_id in pending_ids

    # 4. Approve
    approve_resp = client.post(
        f"/api/quotes/{quote_id}/approve",
        json={"comments": "Approved after margin assessment"},
        headers=mgr_headers,
    )
    assert approve_resp.status_code == 200
    approval_data = approve_resp.json()
    assert approval_data["status"] == "APPROVED"
    assert approval_data["comments"] == "Approved after margin assessment"

    # 5. Check quote status is now APPROVED
    quote_resp = client.get(f"/api/quotes/{quote_id}", headers=mgr_headers)
    assert quote_resp.json()["status"] == "APPROVED"


def test_13_manager_rejection_flow(client: TestClient):
    """Scenario 13: Sales Manager rejects quote and it becomes REJECTED."""
    rep_token = get_auth_token(client, "salesrep@dealflow360.internal")
    rep_headers = {"Authorization": f"Bearer {rep_token}"}

    create_resp = client.post(
        "/api/quotes",
        json={
            "customer_id": 1,
            "lines": [
                {"product_id": 3, "quantity": 1, "discount_percent": 18.0},
            ],
        },
        headers=rep_headers,
    )
    quote_id = create_resp.json()["id"]

    mgr_token = get_auth_token(client, "salesmgr@dealflow360.internal")
    mgr_headers = {"Authorization": f"Bearer {mgr_token}"}

    reject_resp = client.post(
        f"/api/quotes/{quote_id}/reject",
        json={"comments": "Discount excessive for standard tier"},
        headers=mgr_headers,
    )
    assert reject_resp.status_code == 200
    assert reject_resp.json()["status"] == "REJECTED"

    quote_resp = client.get(f"/api/quotes/{quote_id}", headers=mgr_headers)
    assert quote_resp.json()["status"] == "REJECTED"


def test_14_quote_status_transitions(client: TestClient):
    """Scenario 14: Validates proper quote state transitions."""
    rep_token = get_auth_token(client, "salesrep@dealflow360.internal")
    rep_headers = {"Authorization": f"Bearer {rep_token}"}

    # Create empty quote -> starts in DRAFT
    create_resp = client.post("/api/quotes", json={"customer_id": 1, "lines": []}, headers=rep_headers)
    quote = create_resp.json()
    assert quote["status"] == "DRAFT"

    # Update with policy violation -> transitions to PENDING_APPROVAL
    update_resp = client.patch(
        f"/api/quotes/{quote['id']}",
        json={"lines": [{"product_id": 3, "quantity": 1, "discount_percent": 18.0}]},
        headers=rep_headers,
    )
    assert update_resp.json()["status"] == "PENDING_APPROVAL"


def test_15_rbac_enforcement(client: TestClient):
    """Scenario 15: Strict RBAC verification across roles."""
    rep_token = get_auth_token(client, "salesrep@dealflow360.internal")
    rep_headers = {"Authorization": f"Bearer {rep_token}"}

    create_resp = client.post(
        "/api/quotes",
        json={"customer_id": 1, "lines": [{"product_id": 3, "quantity": 1, "discount_percent": 18.0}]},
        headers=rep_headers,
    )
    quote_id = create_resp.json()["id"]

    # Sales Rep attempts to approve own quote -> FORBIDDEN (403)
    rep_approve = client.post(f"/api/quotes/{quote_id}/approve", headers=rep_headers)
    assert rep_approve.status_code == 403
    assert rep_approve.json()["error"]["code"] == "FORBIDDEN"

    # Customer attempts to approve quote -> FORBIDDEN (403)
    cust_token = get_auth_token(client, "customer@acmecorp.com")
    cust_headers = {"Authorization": f"Bearer {cust_token}"}
    cust_approve = client.post(f"/api/quotes/{quote_id}/approve", headers=cust_headers)
    assert cust_approve.status_code == 403


def test_16_audit_log_creation(client: TestClient, db_session: Session):
    """Scenario 16: Verifies AuditLog records for Quote and Approval lifecycle events."""
    rep_token = get_auth_token(client, "salesrep@dealflow360.internal")
    rep_headers = {"Authorization": f"Bearer {rep_token}"}

    create_resp = client.post(
        "/api/quotes",
        json={
            "customer_id": 1,
            "lines": [
                {"product_id": 1, "quantity": 10, "discount_percent": 8.0},
                {"product_id": 3, "quantity": 1, "discount_percent": 18.0},
            ],
        },
        headers=rep_headers,
    )
    quote_id = create_resp.json()["id"]

    mgr_token = get_auth_token(client, "salesmgr@dealflow360.internal")
    mgr_headers = {"Authorization": f"Bearer {mgr_token}"}
    client.post(f"/api/quotes/{quote_id}/approve", json={"comments": "Looks good"}, headers=mgr_headers)

    # Check AuditLog database entries
    logs = db_session.query(AuditLog).filter(AuditLog.entity_id == quote_id).all()
    actions = [log.action for log in logs]

    assert "QUOTE_CREATED" in actions
    assert "RISK_EVALUATED" in actions
    assert "QUOTE_APPROVED" in actions
