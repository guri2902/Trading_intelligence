from fastapi.testclient import TestClient

from backend.app.main import app

client = TestClient(app)


def test_history_endpoint_shape():
    response = client.get("/ui/history")
    assert response.status_code == 200
    body = response.json()
    assert "records" in body
    assert "summary" in body
    assert "count" in body


def test_system_status_endpoint_shape():
    response = client.get("/ui/system-status")
    assert response.status_code == 200
    body = response.json()
    assert body["backend"] in {"CONNECTED", "UNAVAILABLE"} or "backend" in body
    assert "realtime_pipeline" in body
    assert "paper" in body


def test_data_quality_endpoint_shape():
    response = client.get("/ui/data-quality")
    assert response.status_code == 200
    assert "events" in response.json()
