from fastapi.testclient import TestClient


def test_app_starts_and_root(client: TestClient):
    """Verifies that the application starts and root endpoint responds."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "name" in data
    assert data["name"] == "DealFlow360 API"


def test_health_check(client: TestClient):
    """Verifies the health check endpoint and database connectivity check."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "ok"
    assert data["database"] == "connected"
    assert "version" in data
