"""
Смоук-тесты API без сети OpenRouter.
Запуск из корня: PYTHONPATH=. python3 -m pytest tests/test_api_smoke.py -v
"""
import os
import sys
from pathlib import Path

import pytest

# Корень репозитория в PYTHONPATH
ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

os.environ.setdefault("DATABASE_URL", f"sqlite:///{ROOT / 'data' / 'test_api_smoke.sqlite3'}")


@pytest.fixture()
def client():
    from fastapi.testclient import TestClient
    from api.database import Base, engine
    from api.main import app

    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    from api.services.catalog_sync import sync_process_catalog
    from sqlalchemy.orm import sessionmaker

    Session = sessionmaker(bind=engine)
    db = Session()
    try:
        sync_process_catalog(db)
    finally:
        db.close()

    with TestClient(app) as c:
        yield c


def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200
    assert r.json()["status"] == "ok"


def test_catalog_not_empty(client):
    r = client.get("/api/v1/catalog/processes")
    assert r.status_code == 200
    data = r.json()
    assert len(data) >= 1
    assert "priority" in data[0] and "process_name" in data[0]


def test_dashboard_empty_db(client):
    r = client.get("/api/v1/dashboard/process-bubbles")
    assert r.status_code == 200
    assert r.json()["items"] == []


def test_heatmap_requires_process(client):
    r = client.get("/api/v1/dashboard/heatmap")
    assert r.status_code == 422


def test_heatmap_actor_process_empty_db(client):
    r = client.get("/api/v1/dashboard/heatmap-actor-process")
    assert r.status_code == 200
    body = r.json()
    assert body["matrix"] == []
    assert body["actors"] == []
    assert body["subprocess_labels"] == []
    assert body["column_process_ids"] == []
    assert body["column_keys"] == []


def test_top_actor_process_empty_db(client):
    r = client.get("/api/v1/dashboard/top-actor-process")
    assert r.status_code == 200
    assert r.json()["items"] == []


def test_actor_process_documents_empty(client):
    r = client.get(
        "/api/v1/dashboard/actor-process-documents",
        params={"process_id": 1, "actor": "__no_such_actor__"},
    )
    assert r.status_code == 200
    assert r.json()["items"] == []


def test_document_404(client):
    r = client.get("/api/v1/documents/by-hash/" + "a" * 64)
    assert r.status_code == 404


def test_document_by_id_404(client):
    r = client.get("/api/v1/documents/by-id/999999")
    assert r.status_code == 404


def test_upload_without_openrouter_key_returns_error_status(client, monkeypatch):
    monkeypatch.setattr("api.services.ingest.OPENROUTER_API_KEY", None)
    r = client.post(
        "/api/v1/documents/upload",
        files={"file": ("t.txt", b"hello", "text/plain")},
    )
    assert r.status_code == 200
    body = r.json()
    assert body.get("status") == "error"
    assert body.get("document", {}).get("processing_status") == "error"


def test_delete_document_404(client):
    r = client.delete("/api/v1/documents/by-id/999999")
    assert r.status_code == 404


def test_delete_document_ok(client, monkeypatch):
    monkeypatch.setattr("api.services.ingest.OPENROUTER_API_KEY", None)
    up = client.post(
        "/api/v1/documents/upload",
        files={"file": ("delme.txt", b"bye", "text/plain")},
    )
    assert up.status_code == 200
    doc_id = up.json()["document"]["id"]

    r = client.delete(f"/api/v1/documents/by-id/{doc_id}")
    assert r.status_code == 200
    assert r.json() == {"deleted": True, "id": doc_id}

    assert client.get(f"/api/v1/documents/by-id/{doc_id}").status_code == 404
