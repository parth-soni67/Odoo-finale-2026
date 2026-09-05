import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.models.quote import Quote, QuoteLine, QuoteStatus
from app.models.product import Product
from app.models.customer import Customer
from app.models.order import OrderStatus

def create_mock_quote(db_session: Session) -> Quote:
    customer = db_session.query(Customer).first()
    product = db_session.query(Product).filter(Product.sku == "HW-IOT-100").first()
    
    quote = Quote(
        quote_number="QT-TEST-001",
        customer_id=customer.id,
        created_by=2, # sales rep
        status=QuoteStatus.APPROVED,
        total_amount=12000.0
    )
    db_session.add(quote)
    db_session.flush()
    
    line = QuoteLine(
        quote_id=quote.id,
        product_id=product.id,
        quantity=10,
        unit_price=product.unit_price,
        discount_percent=0.0,
        line_total=12000.0,
        line_type="ONE_TIME"
    )
    db_session.add(line)
    db_session.commit()
    return quote

def test_create_order_success(client: TestClient, db_session: Session):
    quote = create_mock_quote(db_session)
    
    login_response = client.post("/api/auth/login", json={"email": "salesrep@dealflow360.internal", "password": "Demo1234!"})
    token = login_response.json()["access_token"]
    
    response = client.post(
        "/api/orders",
        json={"quote_id": quote.id},
        headers={"Authorization": f"Bearer {token}"}
    )
    
    assert response.status_code == 201
    data = response.json()
    assert data["quote_id"] == quote.id
    assert data["status"] == "PENDING"
    assert len(data["lines"]) == 1

def test_get_order(client: TestClient, db_session: Session):
    quote = create_mock_quote(db_session)
    login_response = client.post("/api/auth/login", json={"email": "salesrep@dealflow360.internal", "password": "Demo1234!"})
    token = login_response.json()["access_token"]
    
    create_resp = client.post(
        "/api/orders",
        json={"quote_id": quote.id},
        headers={"Authorization": f"Bearer {token}"}
    )
    order_id = create_resp.json()["id"]
    
    response = client.get(
        f"/api/orders/{order_id}",
        headers={"Authorization": f"Bearer {token}"}
    )
    assert response.status_code == 200
    assert response.json()["id"] == order_id
