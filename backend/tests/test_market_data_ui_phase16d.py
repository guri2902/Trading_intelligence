from fastapi.testclient import TestClient
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from backend.app.db.models import Base, Instrument, MarketSnapshot
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


def test_option_chain_empty_is_explicit():
    response = client.get("/ui/option-chain", params={"underlying": "NIFTY"})
    assert response.status_code == 200
    body = response.json()
    assert body["underlying"] == "NIFTY"
    assert body["rows"] == []


def test_scanner_endpoint_returns_backend_shape():
    response = client.get("/ui/scanner")
    assert response.status_code == 200
    body = response.json()
    assert "rows" in body
    assert "pipeline_running" in body
    assert "last_error" in body
