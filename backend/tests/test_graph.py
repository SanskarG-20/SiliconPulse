from fastapi.testclient import TestClient

from app.core.auth import get_current_user
from app.main import app

app.dependency_overrides[get_current_user] = lambda: {"user_id": "test_user", "email": "test@example.com"}

client = TestClient(app)


def test_graph_nodes():
    resp = client.get("/api/graph/nodes")
    assert resp.status_code == 200
    data = resp.json()
    assert "nodes" in data
    assert "TSMC" in data["nodes"]
    assert "NVIDIA" in data["nodes"]


def test_graph_edges():
    resp = client.get("/api/graph/edges")
    assert resp.status_code == 200
    data = resp.json()
    assert "edges" in data
    assert len(data["edges"]) >= 10
    assert any(e["source"] == "ASML" and e["target"] == "TSMC" for e in data["edges"])


def test_graph_impact_tsmc():
    resp = client.get("/api/graph/impact/TSMC")
    assert resp.status_code == 200
    data = resp.json()
    assert data["company"] == "TSMC"
    assert "NVIDIA" in data["impact"]
    assert data["impact"]["NVIDIA"]["score"] > 0.5
    # depth 2 should include Microsoft via NVIDIA
    assert "Microsoft" in data["impact"]


def test_graph_suppliers_nvidia():
    resp = client.get("/api/graph/suppliers/NVIDIA")
    assert resp.status_code == 200
    data = resp.json()
    assert data["company"] == "NVIDIA"
    assert "TSMC" in data["suppliers"]
    assert "ASML" in data["suppliers"]  # ASML -> TSMC -> NVIDIA


def test_graph_404():
    resp = client.get("/api/graph/impact/UnknownCompanyXYZ")
    assert resp.status_code == 404
