from fastapi.testclient import TestClient
from app.models.user import Role
from app.core.security import create_access_token
from app.core.dependencies import require_roles
from fastapi import APIRouter, Depends
from app.main import app

# Add a test router for verifying RBAC enforcement
rbac_test_router = APIRouter(prefix="/api/test-rbac", tags=["Test RBAC"])


@rbac_test_router.get("/admin-only")
def admin_only_endpoint(user=Depends(require_roles(Role.ADMIN))):
    return {"message": "Welcome Admin", "user_id": user.id}


@rbac_test_router.get("/finance-or-manager")
def finance_or_manager_endpoint(
    user=Depends(require_roles(Role.FINANCE, Role.SALES_MANAGER))
):
    return {"message": "Welcome Manager or Finance", "user_id": user.id}


app.include_router(rbac_test_router)


def test_login_success(client: TestClient):
    """Verifies that an existing seeded user can authenticate successfully."""
    response = client.post(
        "/api/auth/login",
        json={"email": "admin@dealflow360.internal", "password": "Demo1234!"}
    )
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert data["user"]["email"] == "admin@dealflow360.internal"
    assert data["user"]["role"] == "ADMIN"


def test_login_invalid_password(client: TestClient):
    """Verifies that incorrect credentials return 401 with standard error structure."""
    response = client.post(
        "/api/auth/login",
        json={"email": "admin@dealflow360.internal", "password": "WrongPassword!"}
    )
    assert response.status_code == 401
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "INVALID_CREDENTIALS"


def test_login_nonexistent_user(client: TestClient):
    """Verifies that nonexistent users return 401 with standard error structure."""
    response = client.post(
        "/api/auth/login",
        json={"email": "nonexistent@dealflow360.internal", "password": "Demo1234!"}
    )
    assert response.status_code == 401
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "INVALID_CREDENTIALS"


def test_get_me_authenticated(client: TestClient):
    """Verifies that GET /api/auth/me returns the authenticated user profile."""
    # Login first
    login_resp = client.post(
        "/api/auth/login",
        json={"email": "salesrep@dealflow360.internal", "password": "Demo1234!"}
    )
    token = login_resp.json()["access_token"]

    # Request /api/auth/me with bearer token
    headers = {"Authorization": f"Bearer {token}"}
    me_resp = client.get("/api/auth/me", headers=headers)
    assert me_resp.status_code == 200
    data = me_resp.json()
    assert data["email"] == "salesrep@dealflow360.internal"
    assert data["role"] == "SALES_REP"
    assert data["full_name"] == "Sam Representative"


def test_get_me_unauthenticated(client: TestClient):
    """Verifies that GET /api/auth/me without token returns 401."""
    response = client.get("/api/auth/me")
    assert response.status_code == 401
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "AUTHENTICATION_REQUIRED"


def test_rbac_admin_allowed_for_admin(client: TestClient):
    """Verifies that ADMIN role can access admin-only endpoint."""
    login_resp = client.post(
        "/api/auth/login",
        json={"email": "admin@dealflow360.internal", "password": "Demo1234!"}
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get("/api/test-rbac/admin-only", headers=headers)
    assert response.status_code == 200
    assert response.json()["message"] == "Welcome Admin"


def test_rbac_admin_forbidden_for_sales_rep(client: TestClient):
    """Verifies that SALES_REP role is forbidden from admin-only endpoint."""
    login_resp = client.post(
        "/api/auth/login",
        json={"email": "salesrep@dealflow360.internal", "password": "Demo1234!"}
    )
    token = login_resp.json()["access_token"]
    headers = {"Authorization": f"Bearer {token}"}

    response = client.get("/api/test-rbac/admin-only", headers=headers)
    assert response.status_code == 403
    data = response.json()
    assert "error" in data
    assert data["error"]["code"] == "FORBIDDEN"


def test_rbac_multi_role_allow_and_deny(client: TestClient):
    """Verifies multi-role endpoint allows FINANCE, but denies SALES_REP."""
    # 1. Finance user -> Allowed
    fin_login = client.post(
        "/api/auth/login",
        json={"email": "finance@dealflow360.internal", "password": "Demo1234!"}
    )
    fin_token = fin_login.json()["access_token"]
    fin_resp = client.get(
        "/api/test-rbac/finance-or-manager",
        headers={"Authorization": f"Bearer {fin_token}"}
    )
    assert fin_resp.status_code == 200

    # 2. Sales Rep -> Forbidden
    rep_login = client.post(
        "/api/auth/login",
        json={"email": "salesrep@dealflow360.internal", "password": "Demo1234!"}
    )
    rep_token = rep_login.json()["access_token"]
    rep_resp = client.get(
        "/api/test-rbac/finance-or-manager",
        headers={"Authorization": f"Bearer {rep_token}"}
    )
    assert rep_resp.status_code == 403
    assert rep_resp.json()["error"]["code"] == "FORBIDDEN"
