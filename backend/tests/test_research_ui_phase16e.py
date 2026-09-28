from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def test_analysis_endpoint_has_stable_shape():
    response = client.get("/ui/analysis")
    assert response.status_code == 200
    body = response.json()
    assert "available" in body
    assert "external" in body
    assert "technical" in body
    assert "structure" in body


def test_ai_analysis_endpoint_has_stable_shape():
    response = client.get("/ui/ai-analysis")
    assert response.status_code == 200
    body = response.json()
    assert "available" in body
    assert "agents" in body or "reason" in body


def test_risk_endpoint_has_stable_shape():
    response = client.get("/ui/risk")
    assert response.status_code == 200
    body = response.json()
    assert "config" in body
    assert "trading_allowed" in body
