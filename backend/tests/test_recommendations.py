"""Automated Test Suite for M6 Upsell & Cross-Sell Recommendations.

Validates:
1. Valid quote returns recommendations.
2. Existing quote products are excluded.
3. Recommendations contain types UPSELL or CROSS_SELL.
4. Recommendations contain explanatory reasons.
5. Recommendations contain estimated margin impact.
6. Quotes with all catalog products return an empty list.
7. Nonexistent quote returns standardized 404 error.
8. Unauthenticated requests return 401.
9. Database persistence to Recommendation model.
"""

import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from app.models.quote import Recommendation


def get_auth_token(client: TestClient, email: str = "salesrep@dealflow360.internal", password: str = "Demo1234!") -> str:
    """Helper to authenticate and return a bearer access token."""
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, f"Login failed for {email}: {resp.text}"
    return resp.json()["access_token"]


def test_valid_quote_returns_recommendations(client: TestClient):
    """Scenario 1: Valid quote containing Edge IoT Gateway returns recommendations."""
    token = get_auth_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    # Create quote containing Edge IoT Gateway Server (Product 1)
    create_resp = client.post(
        "/api/quotes",
        json={
            "customer_id": 1,
            "lines": [
                {"product_id": 1, "quantity": 5, "discount_percent": 5.0}
            ],
        },
        headers=headers,
    )
    assert create_resp.status_code == 201
    quote_id = create_resp.json()["id"]

    # Request recommendations
    rec_resp = client.get(f"/api/quotes/{quote_id}/recommendations", headers=headers)
    assert rec_resp.status_code == 200
    data = rec_resp.json()

    assert data["quote_id"] == quote_id
    assert isinstance(data["recommendations"], list)
    assert len(data["recommendations"]) > 0


def test_existing_quote_products_are_excluded(client: TestClient):
    """Scenario 2: Products already selected in the quote are excluded from recommendations."""
    token = get_auth_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    # Create quote with Product 1
    create_resp = client.post(
        "/api/quotes",
        json={
            "customer_id": 1,
            "lines": [{"product_id": 1, "quantity": 2, "discount_percent": 0.0}],
        },
        headers=headers,
    )
    quote_id = create_resp.json()["id"]

    rec_resp = client.get(f"/api/quotes/{quote_id}/recommendations", headers=headers)
    assert rec_resp.status_code == 200
    data = rec_resp.json()

    rec_product_ids = [r["product_id"] for r in data["recommendations"]]
    assert 1 not in rec_product_ids, "Product 1 is already in the quote and must not be recommended"


def test_recommendation_types_upsell_and_cross_sell(client: TestClient):
    """Scenario 3: Recommendations contain valid types (UPSELL or CROSS_SELL)."""
    token = get_auth_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    # Quote with Edge IoT Gateway (Hardware)
    create_resp = client.post(
        "/api/quotes",
        json={
            "customer_id": 1,
            "lines": [{"product_id": 1, "quantity": 10, "discount_percent": 5.0}],
        },
        headers=headers,
    )
    quote_id = create_resp.json()["id"]

    rec_resp = client.get(f"/api/quotes/{quote_id}/recommendations", headers=headers)
    assert rec_resp.status_code == 200
    recs = rec_resp.json()["recommendations"]

    rec_types = {r["type"] for r in recs}
    assert all(t in ["UPSELL", "CROSS_SELL"] for t in rec_types)

    # For hardware quote: Platform license should be UPSELL, SLA Support should be CROSS_SELL
    assert "UPSELL" in rec_types, "Expected an UPSELL recommendation (e.g. Enterprise Platform License)"
    assert "CROSS_SELL" in rec_types, "Expected a CROSS_SELL recommendation (e.g. SLA Support)"


def test_recommendation_contains_reason(client: TestClient):
    """Scenario 4: Every recommendation contains an explainable reason."""
    token = get_auth_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    create_resp = client.post(
        "/api/quotes",
        json={
            "customer_id": 1,
            "lines": [{"product_id": 1, "quantity": 1, "discount_percent": 0.0}],
        },
        headers=headers,
    )
    quote_id = create_resp.json()["id"]

    rec_resp = client.get(f"/api/quotes/{quote_id}/recommendations", headers=headers)
    assert rec_resp.status_code == 200
    for r in rec_resp.json()["recommendations"]:
        assert r["reason"] is not None
        assert len(r["reason"].strip()) > 10, f"Reason too brief or missing: {r}"


def test_recommendation_contains_margin_impact(client: TestClient):
    """Scenario 5: Every recommendation includes correct estimated margin impact."""
    token = get_auth_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    # Quote with Hardware
    create_resp = client.post(
        "/api/quotes",
        json={
            "customer_id": 1,
            "lines": [{"product_id": 1, "quantity": 1, "discount_percent": 0.0}],
        },
        headers=headers,
    )
    quote_id = create_resp.json()["id"]

    rec_resp = client.get(f"/api/quotes/{quote_id}/recommendations", headers=headers)
    assert rec_resp.status_code == 200
    recs = rec_resp.json()["recommendations"]

    # Verify Platform License (Product 2: Unit Price 5000, Cost 500 -> Margin 4500)
    platform_rec = next((r for r in recs if r["product_id"] == 2), None)
    if platform_rec:
        assert platform_rec["unit_price"] == 5000.0
        assert platform_rec["estimated_margin_impact"] == 4500.0
        assert platform_rec["type"] == "UPSELL"

    # Verify 24/7 SLA Support (Product 4: Unit Price 800, Cost 200 -> Margin 600)
    sla_rec = next((r for r in recs if r["product_id"] == 4), None)
    if sla_rec:
        assert sla_rec["unit_price"] == 800.0
        assert sla_rec["estimated_margin_impact"] == 600.0
        assert sla_rec["type"] == "CROSS_SELL"


def test_no_recommendations_when_all_products_in_quote(client: TestClient):
    """Scenario 6: Returns empty list when all catalog products are already in the quote."""
    token = get_auth_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    # Create quote with all 4 seeded products
    create_resp = client.post(
        "/api/quotes",
        json={
            "customer_id": 1,
            "lines": [
                {"product_id": 1, "quantity": 1, "discount_percent": 0.0},
                {"product_id": 2, "quantity": 1, "discount_percent": 0.0},
                {"product_id": 3, "quantity": 1, "discount_percent": 0.0},
                {"product_id": 4, "quantity": 1, "discount_percent": 0.0},
            ],
        },
        headers=headers,
    )
    quote_id = create_resp.json()["id"]

    rec_resp = client.get(f"/api/quotes/{quote_id}/recommendations", headers=headers)
    assert rec_resp.status_code == 200
    data = rec_resp.json()
    assert data["quote_id"] == quote_id
    assert data["recommendations"] == []


def test_nonexistent_quote_returns_404(client: TestClient):
    """Scenario 7: Requesting recommendations for nonexistent quote returns 404."""
    token = get_auth_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    resp = client.get("/api/quotes/999999/recommendations", headers=headers)
    assert resp.status_code == 404
    data = resp.json()
    assert "error" in data
    assert data["error"]["code"] == "QUOTE_NOT_FOUND"


def test_recommendations_unauthenticated(client: TestClient):
    """Scenario 8: Unauthenticated request returns 401."""
    resp = client.get("/api/quotes/1/recommendations")
    assert resp.status_code == 401
    assert "error" in resp.json()
    assert resp.json()["error"]["code"] == "AUTHENTICATION_REQUIRED"


def test_persisted_recommendations_in_database(client: TestClient, db_session: Session):
    """Scenario 9: Recommendations are persisted to existing Recommendation table."""
    token = get_auth_token(client)
    headers = {"Authorization": f"Bearer {token}"}

    create_resp = client.post(
        "/api/quotes",
        json={
            "customer_id": 1,
            "lines": [{"product_id": 1, "quantity": 2, "discount_percent": 0.0}],
        },
        headers=headers,
    )
    quote_id = create_resp.json()["id"]

    # Trigger recommendation endpoint
    client.get(f"/api/quotes/{quote_id}/recommendations", headers=headers)

    # Verify DB query
    db_recs = db_session.query(Recommendation).filter(Recommendation.quote_id == quote_id).all()
    assert len(db_recs) > 0
    types = [r.recommendation_type for r in db_recs]
    assert "UPSELL" in types or "CROSS_SELL" in types
