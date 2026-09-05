import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.models.quote import Quote, QuoteLine, QuoteStatus
from app.models.product import Product
from app.models.customer import Customer
from app.models.order import OrderStatus

def create_mock_hybrid_quote_and_order(db_session: Session, client: TestClient, token: str):
    customer = db_session.query(Customer).first()
    hw_product = db_session.query(Product).filter(Product.sku == "HW-IOT-100").first()
    sw_product = db_session.query(Product).filter(Product.sku == "SUB-SUPP-247").first()
    
    quote = Quote(
        quote_number="QT-TEST-HYBRID-001",
        customer_id=customer.id,
        created_by=2, # sales rep
        status=QuoteStatus.APPROVED,
        total_amount=hw_product.unit_price + sw_product.unit_price
    )
    db_session.add(quote)
    db_session.flush()
    
    line1 = QuoteLine(
        quote_id=quote.id,
        product_id=hw_product.id,
        quantity=1,
        unit_price=hw_product.unit_price,
        discount_percent=0.0,
        line_total=hw_product.unit_price,
        line_type="ONE_TIME"
    )
    
    line2 = QuoteLine(
        quote_id=quote.id,
        product_id=sw_product.id,
        quantity=1,
        unit_price=sw_product.unit_price,
        discount_percent=0.0,
        line_total=sw_product.unit_price,
        line_type="RECURRING"
    )
    db_session.add_all([line1, line2])
    db_session.commit()
    
    resp = client.post(
        "/api/orders",
        json={"quote_id": quote.id},
        headers={"Authorization": f"Bearer {token}"}
    )
    return resp.json()["id"]

def test_hybrid_billing_generation(client: TestClient, db_session: Session):
    login_response = client.post("/api/auth/login", json={"email": "finance@dealflow360.internal", "password": "Demo1234!"})
    finance_token = login_response.json()["access_token"]
    login_response = client.post("/api/auth/login", json={"email": "salesrep@dealflow360.internal", "password": "Demo1234!"})
    sales_token = login_response.json()["access_token"]
    
    order_id = create_mock_hybrid_quote_and_order(db_session, client, sales_token)
    
    # Generate billing
    response = client.post(
        f"/api/orders/{order_id}/billing",
        headers={"Authorization": f"Bearer {finance_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert len(data["invoices"]) == 1
    assert len(data["subscriptions"]) == 1
    
    invoice = data["invoices"][0]
    assert invoice["billing_type"] == "ONE_TIME"
    assert invoice["status"] == "DRAFT"
    
    subscription = data["subscriptions"][0]
    assert subscription["status"] == "ACTIVE"

def test_simulated_payment(client: TestClient, db_session: Session):
    login_response = client.post("/api/auth/login", json={"email": "finance@dealflow360.internal", "password": "Demo1234!"})
    finance_token = login_response.json()["access_token"]
    login_response = client.post("/api/auth/login", json={"email": "salesrep@dealflow360.internal", "password": "Demo1234!"})
    sales_token = login_response.json()["access_token"]
    
    order_id = create_mock_hybrid_quote_and_order(db_session, client, sales_token)
    
    billing_resp = client.post(
        f"/api/orders/{order_id}/billing",
        headers={"Authorization": f"Bearer {finance_token}"}
    )
    invoice = billing_resp.json()["invoices"][0]
    invoice_id = invoice["id"]
    amount = invoice["total_amount"]
    
    # Process payment
    pay_resp = client.post(
        f"/api/orders/{order_id}/payment",
        json={"invoice_id": invoice_id, "amount": amount, "payment_method": "DEMO_CARD"},
        headers={"Authorization": f"Bearer {finance_token}"}
    )
    assert pay_resp.status_code == 200
    data = pay_resp.json()
    assert data["payment_status"] == "SUCCESSFUL"
    
    # Check invoice status
    inv_resp = client.get(
        f"/api/orders/{order_id}/billing",
        headers={"Authorization": f"Bearer {finance_token}"}
    )
    assert inv_resp.json()["invoices"][0]["status"] == "PAID"
