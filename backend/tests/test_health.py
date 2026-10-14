"""Health endpoint and import boundary checks."""

from __future__ import annotations

import sys

from app.main import app
from fastapi.testclient import TestClient


def test_health_ok() -> None:
    response = TestClient(app).get("/health")
    assert response.status_code == 200
    body = response.json()
    assert body == {"status": "ok"}
    assert "key" not in body
    assert "JEV" not in response.text


def test_health_allows_local_frontend_origin() -> None:
    response = TestClient(app).get(
        "/health",
        headers={"Origin": "http://localhost:5173"},
    )
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"


def test_health_rejects_unknown_origin() -> None:
    response = TestClient(app).get(
        "/health",
        headers={"Origin": "https://example.com"},
    )
    assert "access-control-allow-origin" not in response.headers


def test_backend_does_not_import_streamlit() -> None:
    assert "streamlit" not in sys.modules
