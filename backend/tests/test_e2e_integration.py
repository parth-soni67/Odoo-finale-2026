import pytest
from fastapi.testclient import TestClient
from app.main import app
from app.core.database import SessionLocal, Base, engine
from seed.seed_data import seed_database


@pytest.fixture(scope="module", autouse=True)
def init_db():
    Base.metadata.create_all(bind=engine)
    db = SessionLocal()
    seed_database(db)
    db.close()


def test_full_e2e_sales_operations_workflow():
    """Executes the end-to-end 15-step DealFlow360 business workflow.

    1. Login Sales Rep
    2. Select Customer
    3. Create Quote (One-Time + Recurring lines)
    4. Apply Discount & Risk Evaluation
    5. Manager Approval
    6. Create Order from Approved Quote
    7. Multi-Warehouse Fulfillment (Suggest & Confirm)
    8. Generate Billing (Invoices + Subscriptions)
    9. Simulated Payment
    10. Customer Portal Login & Access
    11. Customer Negotiation Request
    12. Manager Review & Approval of Negotiation
    13. Quote Re-Approval
    14. Customer Confirmation
    15. Deal Health Scoring & Diagnostics
    """
    with TestClient(app) as client:
        # Step 1: Login Sales Rep
        r = client.post(
            "/api/auth/login",
            json={"email": "salesrep@dealflow360.internal", "password": "Demo1234!"}
        )
        assert r.status_code == 200, f"Login failed: {r.text}"
        rep_token = r.json()["access_token"]
        rep_headers = {"Authorization": f"Bearer {rep_token}"}

        # Step 2: Select Customer
        r = client.get("/api/customers", headers=rep_headers)
        assert r.status_code == 200 and len(r.json()) > 0
        customer = r.json()[0]
        customer_id = customer["id"]

        # Step 3: Create Quote with One-Time and Recurring products
        quote_payload = {
            "customer_id": customer_id,
            "lines": [
                {
                    "product_id": 1,
                    "quantity": 10,
                    "unit_price": 1200.0,
                    "discount_percent": 15.0,
                    "line_type": "ONE_TIME"
                },
                {
                    "product_id": 4,
                    "quantity": 1,
                    "unit_price": 800.0,
                    "discount_percent": 10.0,
                    "line_type": "RECURRING"
                }
            ]
        }
        r = client.post("/api/quotes", json=quote_payload, headers=rep_headers)
        assert r.status_code == 201, f"Create quote failed: {r.text}"
        quote = r.json()
        quote_id = quote["id"]

        # Step 4: Risk Evaluation
        r = client.post(f"/api/quotes/{quote_id}/risk", headers=rep_headers)
        assert r.status_code == 200, f"Risk eval failed: {r.text}"
        risk = r.json()
        assert "risk_score" in risk

        # Step 5: Manager Approval
        r = client.post(
            "/api/auth/login",
            json={"email": "salesmgr@dealflow360.internal", "password": "Demo1234!"}
        )
        mgr_token = r.json()["access_token"]
        mgr_headers = {"Authorization": f"Bearer {mgr_token}"}

        r = client.post(
            f"/api/quotes/{quote_id}/approve",
            json={"comments": "Approved for enterprise demo"},
            headers=mgr_headers
        )
        assert r.status_code == 200, f"Quote approval failed: {r.text}"

        # Step 6: Create Order
        order_payload = {"quote_id": quote_id, "customer_id": customer_id}
        r = client.post("/api/orders", json=order_payload, headers=rep_headers)
        assert r.status_code == 201, f"Create order failed: {r.text}"
        order = r.json()
        order_id = order["id"]

        # Step 7: Multi-Warehouse Fulfillment (Operations Role)
        r = client.post(
            "/api/auth/login",
            json={"email": "ops@dealflow360.internal", "password": "Demo1234!"}
        )
        ops_token = r.json()["access_token"]
        ops_headers = {"Authorization": f"Bearer {ops_token}"}

        r = client.post(f"/api/orders/{order_id}/fulfillment/suggest", headers=ops_headers)
        assert r.status_code == 200, f"Fulfillment suggest failed: {r.text}"
        suggestion = r.json()

        r = client.post(
            f"/api/orders/{order_id}/fulfillment/confirm",
            json=suggestion,
            headers=ops_headers
        )
        assert r.status_code == 200, f"Fulfillment confirm failed: {r.text}"

        # Step 8: Generate Billing (Invoice + Subscription)
        r = client.post(
            "/api/auth/login",
            json={"email": "finance@dealflow360.internal", "password": "Demo1234!"}
        )
        fin_token = r.json()["access_token"]
        fin_headers = {"Authorization": f"Bearer {fin_token}"}

        r = client.post(f"/api/orders/{order_id}/billing", headers=fin_headers)
        assert r.status_code in [200, 201], f"Generate billing failed: {r.text}"
        billing = r.json()
        invoices = billing.get("invoices", [])
        assert len(invoices) > 0, "No invoice generated"
        invoice_id = invoices[0]["id"]
        invoice_amount = invoices[0]["total_amount"]

        # Step 9: Simulated Payment
        payment_payload = {
            "invoice_id": invoice_id,
            "amount": invoice_amount,
            "payment_method": "SIMULATED_CARD"
        }
        r = client.post(
            f"/api/orders/{order_id}/payment",
            json=payment_payload,
            headers=fin_headers
        )
        assert r.status_code == 200, f"Payment failed: {r.text}"
        assert r.json().get("payment_status") == "SUCCESSFUL"

        # Step 10: Customer Portal
        r = client.post(
            "/api/auth/login",
            json={"email": "customer@acmecorp.com", "password": "Demo1234!"}
        )
        cust_token = r.json()["access_token"]
        cust_headers = {"Authorization": f"Bearer {cust_token}"}

        r = client.get(f"/api/portal/quotes/{quote_id}", headers=cust_headers)
        assert r.status_code == 200, f"Portal quote fetch failed: {r.text}"

        # Step 11: Customer Negotiation
        neg_payload = {
            "requested_change": "discount_percent",
            "proposed_value": "18.0"
        }
        r = client.post(
            f"/api/portal/quotes/{quote_id}/negotiate",
            json=neg_payload,
            headers=cust_headers
        )
        assert r.status_code == 201, f"Negotiation submit failed: {r.text}"
        neg_id = r.json()["id"]

        # Step 12: Manager Approval of Negotiation
        r = client.post(
            f"/api/negotiations/{neg_id}/approve",
            json={"comments": "Approved higher discount"},
            headers=mgr_headers
        )
        assert r.status_code == 200, f"Negotiation approve failed: {r.text}"

        # Step 13: Quote Re-Approval
        r = client.post(
            f"/api/quotes/{quote_id}/approve",
            json={"comments": "Re-approved after negotiation"},
            headers=mgr_headers
        )
        assert r.status_code == 200, f"Quote re-approval failed: {r.text}"

        # Step 14: Customer Confirmation
        r = client.post(f"/api/portal/quotes/{quote_id}/confirm", headers=cust_headers)
        assert r.status_code == 200, f"Customer confirm failed: {r.text}"

        # Step 15: Deal Health
        r = client.get(f"/api/deal-health/{quote_id}", headers=rep_headers)
        assert r.status_code == 200, f"Deal health failed: {r.text}"
        health = r.json()
        assert "risk_score" in health
        assert "risk_level" in health
