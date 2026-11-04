from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from scraper import api as api_mod
from scraper.config import ScraperConfig
from scraper.database import MachineStore


@pytest.fixture()
def client(tmp_path: Path, monkeypatch: pytest.MonkeyPatch):
    db_path = tmp_path / "api.db"
    cfg = ScraperConfig(db_path=str(db_path))

    monkeypatch.setattr(api_mod, "load_config", lambda: cfg)
    # recreate app with patched config
    app = api_mod.create_app()
    with TestClient(app) as c:
        yield c


def test_health(client: TestClient):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["ok"] is True


def test_demo_scrape_and_list(client: TestClient):
    r = client.post("/scrape?demo=true")
    assert r.status_code == 200
    body = r.json()
    assert body["ok"] is True
    assert body["count"] >= 1
    assert body["source"] == "demo"

    listed = client.get("/machines")
    assert listed.status_code == 200
    data = listed.json()
    assert data["count"] == body["count"]
    assert any(m["machine_id"] == "207" for m in data["machines"])

    one = client.get("/machines/207")
    assert one.status_code == 200
    assert one.json()["days30_rate"] == 95.62
