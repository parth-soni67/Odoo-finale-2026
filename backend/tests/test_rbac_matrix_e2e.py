"""End-to-End Automated RBAC Matrix and Demo Mode Security Tests.

Covers:
- 6 roles (CUSTOMER, SALES_REP, SALES_MANAGER, FINANCE, OPERATIONS, ADMIN)
- Authorized vs Forbidden routes for each role
- Strict 403 enforcement preventing role escalation
- Demo Login flow validation and authoritative GET /api/auth/me verification
"""

import pytest
from fastapi.testclient import TestClient

from app.models.user import Role


def get_token(client: TestClient, email: str, password: str = "Demo1234!") -> str:
    resp = client.post("/api/auth/login", json={"email": email, "password": password})
    assert resp.status_code == 200, f"Login failed for {email}: {resp.text}"
    return resp.json()["access_token"]


def auth_header(token: str) -> dict:
    return {"Authorization": f"Bearer {token}"}


# ==============================================================================
# 1. CUSTOMER RBAC Tests
# ==============================================================================
def test_customer_allowed_and_forbidden_endpoints(client: TestClient):
    token = get_token(client, "customer@acmecorp.com")
    headers = auth_header(token)

    # Verify authoritative role
    me_resp = client.get("/api/auth/me", headers=headers)
    assert me_resp.status_code == 200
    assert me_resp.json()["role"] == "CUSTOMER"

    # Allowed: Customer Portal Dashboard, Quotes, Orders, Billing, Profile
    assert client.get("/api/portal/dashboard", headers=headers).status_code in [200, 404]
    assert client.get("/api/portal/quotes", headers=headers).status_code in [200, 404]
    assert client.get("/api/portal/orders", headers=headers).status_code in [200, 404]

    # Forbidden: Internal APIs must return 403
    # 1. Customer cannot create quotes directly via internal API
    assert client.post("/api/quotes", json={}, headers=headers).status_code == 403
    # 2. Customer cannot view internal customer registry
    assert client.get("/api/customers", headers=headers).status_code == 403
    # 3. Customer cannot access Deal Health
    assert client.get("/api/deal-health", headers=headers).status_code == 403
    # 4. Customer cannot access Warehouses
    assert client.get("/api/warehouses", headers=headers).status_code == 403
    assert client.post("/api/warehouses", json={"name": "Fake"}, headers=headers).status_code == 403
    # 5. Customer cannot access Inventory
    assert client.get("/api/inventory", headers=headers).status_code == 403
    # 6. Customer cannot approve quotes
    assert client.post("/api/quotes/1/approve", json={}, headers=headers).status_code == 403
    # 7. Customer cannot create products
    assert client.post("/api/products", json={"name": "Hacked"}, headers=headers).status_code == 403


# ==============================================================================
# 2. SALES_REP RBAC Tests
# ==============================================================================
def test_sales_rep_allowed_and_forbidden_endpoints(client: TestClient):
    token = get_token(client, "salesrep@dealflow360.internal")
    headers = auth_header(token)

    me_resp = client.get("/api/auth/me", headers=headers)
    assert me_resp.status_code == 200
    assert me_resp.json()["role"] == "SALES_REP"

    # Allowed: Quotes, Products, Customers, Deal Health
    assert client.get("/api/quotes", headers=headers).status_code == 200
    assert client.get("/api/products", headers=headers).status_code == 200
    assert client.get("/api/customers", headers=headers).status_code == 200
    assert client.get("/api/deal-health", headers=headers).status_code == 200

    # Forbidden:
    # 1. Sales Rep cannot approve quotes
    assert client.post("/api/quotes/1/approve", json={}, headers=headers).status_code == 403
    # 2. Sales Rep cannot create/modify warehouses
    assert client.post("/api/warehouses", json={"name": "Rep WH"}, headers=headers).status_code == 403
    # 3. Sales Rep cannot modify inventory
    assert client.post("/api/inventory/stock", json={"warehouse_id": 1, "product_id": 1, "quantity": 10}, headers=headers).status_code == 403
    assert client.post("/api/warehouses/1/inventory/restock", json={"product_id": 1, "quantity": 5}, headers=headers).status_code == 403
    # 4. Sales Rep cannot create products
    assert client.post("/api/products", json={"name": "Rep Product"}, headers=headers).status_code == 403


# ==============================================================================
# 3. SALES_MANAGER RBAC Tests
# ==============================================================================
def test_sales_manager_allowed_endpoints(client: TestClient):
    token = get_token(client, "salesmgr@dealflow360.internal")
    headers = auth_header(token)

    me_resp = client.get("/api/auth/me", headers=headers)
    assert me_resp.status_code == 200
    assert me_resp.json()["role"] == "SALES_MANAGER"

    # Allowed: Warehouses, Inventory, Quotes, Deal Health, Products, Customers
    assert client.get("/api/warehouses", headers=headers).status_code == 200
    assert client.get("/api/inventory", headers=headers).status_code == 200
    assert client.get("/api/quotes", headers=headers).status_code == 200
    assert client.get("/api/products", headers=headers).status_code == 200
    assert client.get("/api/customers", headers=headers).status_code == 200
    assert client.get("/api/deal-health", headers=headers).status_code == 200

    # Sales Manager can create warehouses and manage inventory
    wh_resp = client.post(
        "/api/warehouses",
        json={"name": "Manager Test WH", "location": "Austin, TX", "is_active": True},
        headers=headers,
    )
    assert wh_resp.status_code == 201


# ==============================================================================
# 4. FINANCE RBAC Tests
# ==============================================================================
def test_finance_allowed_and_forbidden_endpoints(client: TestClient):
    token = get_token(client, "finance@dealflow360.internal")
    headers = auth_header(token)

    me_resp = client.get("/api/auth/me", headers=headers)
    assert me_resp.status_code == 200
    assert me_resp.json()["role"] == "FINANCE"

    # Allowed: Quotes, Customers, Deal Health
    assert client.get("/api/quotes", headers=headers).status_code == 200
    assert client.get("/api/customers", headers=headers).status_code == 200
    assert client.get("/api/deal-health", headers=headers).status_code == 200

    # Forbidden:
    # 1. Finance cannot mutate warehouse stock
    assert client.post("/api/warehouses", json={"name": "Finance WH"}, headers=headers).status_code == 403
    assert client.post("/api/inventory/stock", json={"warehouse_id": 1, "product_id": 1, "quantity": 10}, headers=headers).status_code == 403
    assert client.post("/api/warehouses/1/inventory/restock", json={"product_id": 1, "quantity": 5}, headers=headers).status_code == 403
    # 2. Finance cannot create products
    assert client.post("/api/products", json={"name": "Finance Product"}, headers=headers).status_code == 403


# ==============================================================================
# 5. OPERATIONS RBAC Tests
# ==============================================================================
def test_operations_allowed_and_forbidden_endpoints(client: TestClient):
    token = get_token(client, "ops@dealflow360.internal")
    headers = auth_header(token)

    me_resp = client.get("/api/auth/me", headers=headers)
    assert me_resp.status_code == 200
    assert me_resp.json()["role"] == "OPERATIONS"

    # Allowed: Orders, Warehouses (read), Inventory (read)
    assert client.get("/api/orders", headers=headers).status_code == 200
    assert client.get("/api/warehouses", headers=headers).status_code == 200
    assert client.get("/api/inventory", headers=headers).status_code == 200

    # Forbidden:
    # 1. Operations cannot approve commercial quotes
    assert client.post("/api/quotes/1/approve", json={}, headers=headers).status_code == 403
    # 2. Operations cannot view strategic Deal Health
    assert client.get("/api/deal-health", headers=headers).status_code == 403
    # 3. Operations cannot create new catalog products
    assert client.post("/api/products", json={"name": "Ops Product"}, headers=headers).status_code == 403


# ==============================================================================
# 6. ADMIN RBAC Tests
# ==============================================================================
def test_admin_has_full_access(client: TestClient):
    token = get_token(client, "admin@dealflow360.internal")
    headers = auth_header(token)

    me_resp = client.get("/api/auth/me", headers=headers)
    assert me_resp.status_code == 200
    assert me_resp.json()["role"] == "ADMIN"

    # Admin has unrestricted access across all endpoints
    assert client.get("/api/quotes", headers=headers).status_code == 200
    assert client.get("/api/products", headers=headers).status_code == 200
    assert client.get("/api/customers", headers=headers).status_code == 200
    assert client.get("/api/deal-health", headers=headers).status_code == 200
    assert client.get("/api/warehouses", headers=headers).status_code == 200
    assert client.get("/api/inventory", headers=headers).status_code == 200
    assert client.get("/api/orders", headers=headers).status_code == 200


# ==============================================================================
# 7. Demo Persona Login Flow (No Role Escalation)
# ==============================================================================
@pytest.mark.parametrize(
    "email,expected_role",
    [
        ("customer@acmecorp.com", Role.CUSTOMER),
        ("salesrep@dealflow360.internal", Role.SALES_REP),
        ("salesmgr@dealflow360.internal", Role.SALES_MANAGER),
        ("finance@dealflow360.internal", Role.FINANCE),
        ("ops@dealflow360.internal", Role.OPERATIONS),
        ("admin@dealflow360.internal", Role.ADMIN),
    ],
)
def test_demo_persona_login_authoritative_identity(client: TestClient, email: str, expected_role: Role):
    """Verifies that selecting a demo persona issues a real backend JWT that strictly

    binds to the user's authoritative role with zero role escalation possibility.
    """
    token = get_token(client, email)
    headers = auth_header(token)

    me_resp = client.get("/api/auth/me", headers=headers)
    assert me_resp.status_code == 200
    data = me_resp.json()
    assert data["role"] == expected_role.value
    assert data["email"] == email
