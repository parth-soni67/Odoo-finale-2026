import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.models.quote import Quote, QuoteLine, QuoteStatus
from app.models.product import Product
from app.models.customer import Customer
from app.models.order import OrderStatus

def create_mock_quote_and_order(db_session: Session, client: TestClient, token: str, quantity: int = 20):
    customer = db_session.query(Customer).first()
    product = db_session.query(Product).filter(Product.sku == "HW-IOT-100").first()
    
    quote = Quote(
        quote_number=f"QT-TEST-FULFILL-{quantity}",
        customer_id=customer.id,
        created_by=2, # sales rep
        status=QuoteStatus.APPROVED,
        total_amount=product.unit_price * quantity
    )
    db_session.add(quote)
    db_session.flush()
    
    line = QuoteLine(
        quote_id=quote.id,
        product_id=product.id,
        quantity=quantity,
        unit_price=product.unit_price,
        discount_percent=0.0,
        line_total=product.unit_price * quantity,
        line_type="ONE_TIME"
    )
    db_session.add(line)
    db_session.commit()
    
    resp = client.post(
        "/api/orders",
        json={"quote_id": quote.id},
        headers={"Authorization": f"Bearer {token}"}
    )
    return resp.json()["id"]

def test_suggest_fulfillment(client: TestClient, db_session: Session):
    # Get ops token
    login_response = client.post("/api/auth/login", json={"email": "ops@dealflow360.internal", "password": "Demo1234!"})
    ops_token = login_response.json()["access_token"]
    
    # Get sales rep token to create order
    login_response = client.post("/api/auth/login", json={"email": "salesrep@dealflow360.internal", "password": "Demo1234!"})
    sales_token = login_response.json()["access_token"]
    
    order_id = create_mock_quote_and_order(db_session, client, sales_token, quantity=20)
    
    response = client.post(
        f"/api/orders/{order_id}/fulfillment/suggest",
        headers={"Authorization": f"Bearer {ops_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["order_id"] == order_id
    assert len(data["lines"]) == 1
    allocations = data["lines"][0]["allocations"]
    assert len(allocations) == 2 # splits into A and B
    
    # Inventory was 15 in A, 10 in B. So for 20, 15 from A and 5 from B.
    assert allocations[0]["quantity"] == 15
    assert allocations[1]["quantity"] == 5
    assert data["lines"][0]["backordered_quantity"] == 0

def test_confirm_fulfillment(client: TestClient, db_session: Session):
    login_response = client.post("/api/auth/login", json={"email": "ops@dealflow360.internal", "password": "Demo1234!"})
    ops_token = login_response.json()["access_token"]
    login_response = client.post("/api/auth/login", json={"email": "salesrep@dealflow360.internal", "password": "Demo1234!"})
    sales_token = login_response.json()["access_token"]
    
    order_id = create_mock_quote_and_order(db_session, client, sales_token, quantity=20)
    
    response = client.post(
        f"/api/orders/{order_id}/fulfillment/confirm",
        headers={"Authorization": f"Bearer {ops_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "CONFIRMED"
    
def test_backorder_handling(client: TestClient, db_session: Session):
    login_response = client.post("/api/auth/login", json={"email": "ops@dealflow360.internal", "password": "Demo1234!"})
    ops_token = login_response.json()["access_token"]
    login_response = client.post("/api/auth/login", json={"email": "salesrep@dealflow360.internal", "password": "Demo1234!"})
    sales_token = login_response.json()["access_token"]
    
    # Total inventory is 25. Order 30.
    order_id = create_mock_quote_and_order(db_session, client, sales_token, quantity=30)
    
    response = client.post(
        f"/api/orders/{order_id}/fulfillment/suggest",
        headers={"Authorization": f"Bearer {ops_token}"}
    )
    assert response.status_code == 200
    data = response.json()
    
    assert data["lines"][0]["backordered_quantity"] == 5
