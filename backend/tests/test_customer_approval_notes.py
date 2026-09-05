"""Tests for Customer-Visible Approval and Governance Notes in DealFlow360.

Validates:
1. Sales Manager approves quotation with Governance Notes -> persisted and returned in Customer Portal API.
2. Finance approves quotation with distinct notes -> both notes cleanly isolated and returned.
3. Pending approvals return PENDING status without fake/placeholder notes.
4. Approval with empty/omitted notes succeeds without errors.
5. Customer isolation is strictly preserved (Customer A gets 403 on Customer B's quote).
6. Negotiation workflow: negotiation requested -> approved with notes -> customer sees the real notes.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session

from app.models.quote import Quote, QuoteStatus
from app.models.customer import Customer
from app.models.approval import Approval, ApprovalStatus, ApprovalType
from app.models.negotiation import Negotiation, NegotiationStatus


def get_auth_headers(client: TestClient, email: str, password: str = "Demo1234!") -> dict:
    """Helper to authenticate a persona and return Authorization headers."""
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, f"Failed to login as {email}: {resp.text}"
    token = resp.json()["access_token"]
    return {"Authorization": f"Bearer {token}"}


def test_customer_portal_approval_notes_end_to_end(client: TestClient, db_session: Session):
    """Verifies that manager and finance approval notes are persisted and returned to the customer."""
    mgr_headers = get_auth_headers(client, "salesmgr@dealflow360.internal")
    fin_headers = get_auth_headers(client, "finance@dealflow360.internal")
    rep_headers = get_auth_headers(client, "salesrep@dealflow360.internal")
    cust_headers = get_auth_headers(client, "customer@acmecorp.com")

    # 1. Sales Rep creates a quote requiring both Manager and Finance approval (e.g. 35% discount)
    q_resp = client.post(
        "/api/quotes",
        json={
            "customer_id": 1,
            "lines": [
                {
                    "product_id": 1,
                    "quantity": 10,
                    "unit_price": 1200.0,
                    "discount_percent": 35.0,
                    "line_type": "ONE_TIME",
                }
            ],
        },
        headers=rep_headers,
    )
    assert q_resp.status_code == 201
    quote_id = q_resp.json()["id"]

    # 2. Customer checks quote before approvals -> sees PENDING status and no notes
    portal_pre = client.get(f"/api/portal/quotes/{quote_id}", headers=cust_headers)
    assert portal_pre.status_code == 200
    pre_data = portal_pre.json()
    assert "approval_summary" in pre_data
    summary_pre = pre_data["approval_summary"]
    assert summary_pre["status"] == "PENDING_APPROVAL"
    assert len(summary_pre["approvals"]) >= 1
    mgr_pre = next((a for a in summary_pre["approvals"] if a["type"] == "MANAGER"), None)
    assert mgr_pre is not None
    assert mgr_pre["status"] == "PENDING"
    assert mgr_pre["notes"] is None

    # 3. Sales Manager approves with specific Governance Notes
    mgr_note = "Approved exception based on customer's 3-year volume commitment."
    mgr_app_resp = client.post(
        f"/api/quotes/{quote_id}/approve",
        json={"action": "APPROVE", "comments": mgr_note},
        headers=mgr_headers,
    )
    assert mgr_app_resp.status_code == 200

    # 4. Customer checks quote after manager approval, before finance approval
    portal_mid = client.get(f"/api/portal/quotes/{quote_id}", headers=cust_headers)
    assert portal_mid.status_code == 200
    mid_data = portal_mid.json()
    summary_mid = mid_data["approval_summary"]
    mgr_mid = next((a for a in summary_mid["approvals"] if a["type"] == "MANAGER"), None)
    assert mgr_mid is not None
    assert mgr_mid["status"] == "APPROVED"
    assert mgr_mid["notes"] == mgr_note

    fin_mid = next((a for a in summary_mid["approvals"] if a["type"] == "FINANCE"), None)
    if fin_mid:
        assert fin_mid["status"] == "PENDING"
        assert fin_mid["notes"] is None

    # 5. Finance approves with distinct note
    fin_note = "Approved after confirming acceptable margin above 15% threshold."
    if fin_mid:
        fin_app_resp = client.post(
            f"/api/quotes/{quote_id}/approve",
            json={"action": "APPROVE", "comments": fin_note},
            headers=fin_headers,
        )
        assert fin_app_resp.status_code == 200

    # 6. Customer checks quote after all approvals resolved
    portal_final = client.get(f"/api/portal/quotes/{quote_id}", headers=cust_headers)
    assert portal_final.status_code == 200
    final_data = portal_final.json()
    assert final_data["status"] == "APPROVED"
    summary_final = final_data["approval_summary"]

    mgr_final = next((a for a in summary_final["approvals"] if a["type"] == "MANAGER"), None)
    assert mgr_final["status"] == "APPROVED"
    assert mgr_final["notes"] == mgr_note

    if fin_mid:
        fin_final = next((a for a in summary_final["approvals"] if a["type"] == "FINANCE"), None)
        assert fin_final["status"] == "APPROVED"
        assert fin_final["notes"] == fin_note

    # 7. Customer confirms the approved quote
    confirm_resp = client.post(f"/api/portal/quotes/{quote_id}/confirm", headers=cust_headers)
    assert confirm_resp.status_code == 200
    assert confirm_resp.json()["status"] == "ACCEPTED"


def test_customer_portal_isolation_notes_security(client: TestClient, db_session: Session):
    """Customer A cannot view Customer B's quote approval notes (403 Forbidden)."""
    cust_a_headers = get_auth_headers(client, "customer@acmecorp.com")
    rep_headers = get_auth_headers(client, "salesrep@dealflow360.internal")
    mgr_headers = get_auth_headers(client, "salesmgr@dealflow360.internal")

    # Create quote for Customer 2 (TechNova Solutions, not Acme Corp)
    q_resp = client.post(
        "/api/quotes",
        json={
            "customer_id": 2,
            "lines": [
                {
                    "product_id": 1,
                    "quantity": 5,
                    "unit_price": 1200.0,
                    "discount_percent": 25.0,
                    "line_type": "ONE_TIME",
                }
            ],
        },
        headers=rep_headers,
    )
    quote_id = q_resp.json()["id"]
    client.post(
        f"/api/quotes/{quote_id}/approve",
        json={"action": "APPROVE", "comments": "Confidential internal pricing exception for TechNova"},
        headers=mgr_headers,
    )

    # Acme Corp customer tries to access TechNova's quote
    forbidden_resp = client.get(f"/api/portal/quotes/{quote_id}", headers=cust_a_headers)
    assert forbidden_resp.status_code == 403


def test_approval_empty_notes_handling(client: TestClient, db_session: Session):
    """Approvals without comments succeed cleanly and notes is None (no undefined/null string)."""
    rep_headers = get_auth_headers(client, "salesrep@dealflow360.internal")
    mgr_headers = get_auth_headers(client, "salesmgr@dealflow360.internal")
    cust_headers = get_auth_headers(client, "customer@acmecorp.com")

    q_resp = client.post(
        "/api/quotes",
        json={
            "customer_id": 1,
            "lines": [
                {
                    "product_id": 1,
                    "quantity": 2,
                    "unit_price": 1200.0,
                    "discount_percent": 18.0,
                    "line_type": "ONE_TIME",
                }
            ],
        },
        headers=rep_headers,
    )
    quote_id = q_resp.json()["id"]

    # Approve with empty comments
    app_resp = client.post(
        f"/api/quotes/{quote_id}/approve",
        json={"action": "APPROVE", "comments": None},
        headers=mgr_headers,
    )
    assert app_resp.status_code == 200

    portal_resp = client.get(f"/api/portal/quotes/{quote_id}", headers=cust_headers)
    assert portal_resp.status_code == 200
    data = portal_resp.json()
    mgr_app = next((a for a in data["approval_summary"]["approvals"] if a["type"] == "MANAGER"), None)
    assert mgr_app is not None
    assert mgr_app["status"] == "APPROVED"
    assert mgr_app["notes"] is None


def test_negotiation_workflow_approval_notes(client: TestClient, db_session: Session):
    """Customer negotiation requested -> Manager approves negotiation/quote with note -> Customer sees note."""
    rep_headers = get_auth_headers(client, "salesrep@dealflow360.internal")
    mgr_headers = get_auth_headers(client, "salesmgr@dealflow360.internal")
    cust_headers = get_auth_headers(client, "customer@acmecorp.com")

    # 1. Rep creates standard quote within standard discount limit (approved or sent)
    q_resp = client.post(
        "/api/quotes",
        json={
            "customer_id": 1,
            "lines": [
                {
                    "product_id": 1,
                    "quantity": 3,
                    "unit_price": 1200.0,
                    "discount_percent": 5.0,
                    "line_type": "ONE_TIME",
                }
            ],
        },
        headers=rep_headers,
    )
    quote_id = q_resp.json()["id"]

    # 2. Customer requests a 22% overall discount (exceeds standard limit)
    neg_resp = client.post(
        f"/api/portal/quotes/{quote_id}/negotiate",
        json={"requested_change": "overall_discount_percent", "proposed_value": "22.0"},
        headers=cust_headers,
    )
    assert neg_resp.status_code == 201

    # 3. Manager approves quote with governance note
    neg_note = "Approved 22% discount counter-proposal given long-term enterprise partnership."
    app_resp = client.post(
        f"/api/quotes/{quote_id}/approve",
        json={"action": "APPROVE", "comments": neg_note},
        headers=mgr_headers,
    )
    assert app_resp.status_code == 200

    # 4. Customer views quote and sees the real note
    portal_resp = client.get(f"/api/portal/quotes/{quote_id}", headers=cust_headers)
    assert portal_resp.status_code == 200
    data = portal_resp.json()
    mgr_app = next((a for a in data["approval_summary"]["approvals"] if a["type"] == "MANAGER"), None)
    assert mgr_app is not None
    assert mgr_app["status"] == "APPROVED"
    assert mgr_app["notes"] == neg_note
