from datetime import datetime, timezone

from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.db.audit import AgentPerformance, AgentRun, Base
from backend.app.db.session import get_db
from backend.app.main import app


engine = create_engine("sqlite:///./phase15_test.db", connect_args={"check_same_thread": False})
TestingSession = sessionmaker(bind=engine, expire_on_commit=False)
Base.metadata.create_all(engine)


def override_db():
    db = TestingSession()
    try:
        yield db
    finally:
        db.close()


app.dependency_overrides[get_db] = override_db
client = TestClient(app)


def _payload():
    return {
        "data": {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "market": {"symbol": "NIFTY"},
            "features": {"trend": "up"},
            "structure": {"regime": "bullish"},
            "options": {"chain_fresh": True},
            "strategies": {"best_setup": {"invalidation": 25000}},
            "ml": {},
            "risk": {},
        },
        "research": {
            "symbol": "NIFTY",
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "fundamentals": {"symbol": "NIFTY", "timestamp": datetime.now(timezone.utc).isoformat(), "score": 0, "confidence": 0, "summary": "index proxy", "metrics": {}, "risks": [], "sources": []},
        },
    }


def test_agent_run_persists_and_retrieves():
    r = client.post("/phase15/agent-run", json=_payload())
    assert r.status_code == 200
    run_id = r.json()["id"]
    assert r.json()["result"]["final_decision"]["action"] in {"BUY_CE", "BUY_PE", "WAIT", "NO_TRADE"}

    detail = client.get(f"/phase15/runs/{run_id}")
    assert detail.status_code == 200
    assert detail.json()["agent_records"]


def test_outcome_updates_performance():
    runs = client.get("/phase15/runs").json()
    run_id = runs[0]["id"]
    direction = runs[0]["decision"]["direction"] or "NONE"
    r = client.post("/phase15/outcomes", json={"run_id": run_id, "realized_direction": direction, "pnl": 100})
    assert r.status_code == 200
    p = client.get("/phase15/performance")
    assert p.status_code == 200
    assert p.json()
