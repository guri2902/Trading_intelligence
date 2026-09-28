from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.db.models import Base
from backend.app.db.session import get_db
from backend.app.main import app

engine = create_engine("sqlite:///:memory:")
Base.metadata.create_all(engine)
SessionLocal = sessionmaker(bind=engine)

def override_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

app.dependency_overrides[get_db] = override_db
client = TestClient(app)


def test_health_and_account():
    health = client.get("/paper/health")
    assert health.status_code == 200
    assert health.json()["live_execution"] is False

    account = client.post("/paper/account", json={"account_id": "qa", "starting_equity": 50000})
    assert account.status_code == 200
    assert account.json()["account_id"] == "qa"

    view = client.get("/paper/account", params={"account_id": "qa"})
    assert view.status_code == 200
    assert view.json()["equity"] == 50000


def test_order_positions_fills_and_close():
    client.post("/paper/account", json={"account_id": "qa2", "starting_equity": 50000})

    order = client.post(
        "/paper/orders",
        json={
            "account_id": "qa2",
            "symbol": "NIFTYCE",
            "action": "BUY_CE",
            "option_type": "CE",
            "strike": 25000,
            "expiry": "2026-09-17",
            "quantity": 50,
            "entry_price": 100,
            "stop_loss": 90,
            "target_1": 110,
            "target_2": 120,
        },
    )
    assert order.status_code == 200
    position_id = order.json()["position"]["position_id"]

    positions = client.get("/paper/positions", params={"account_id": "qa2", "status": "OPEN"})
    assert positions.status_code == 200
    assert positions.json()["positions"][0]["position_id"] == position_id

    mark = client.post(
        f"/paper/positions/{position_id}/mark",
        json={"account_id": "qa2", "position_id": position_id, "price": 111},
    )
    assert mark.status_code == 200
    assert mark.json()["position"]["status"] == "CLOSED"

    fills = client.get("/paper/fills", params={"account_id": "qa2"})
    assert fills.status_code == 200
    assert len(fills.json()["fills"]) >= 2

    curve = client.get("/paper/equity-curve", params={"account_id": "qa2"})
    assert curve.status_code == 200
    assert len(curve.json()["points"]) >= 2
