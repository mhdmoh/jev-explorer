"""The API serves the built UI without replacing API routes."""

from __future__ import annotations

from pathlib import Path

from app.main import create_app
from fastapi.testclient import TestClient


def _client(static_dir: Path) -> TestClient:
    return TestClient(create_app(static_dir=static_dir))


def _write_build(static_dir: Path) -> None:
    static_dir.mkdir(parents=True, exist_ok=True)
    (static_dir / "index.html").write_text(
        '<!doctype html><div id="root"></div>'
        '<script type="module" src="/assets/app.js"></script>',
        encoding="utf-8",
    )
    assets = static_dir / "assets"
    assets.mkdir()
    (assets / "app.js").write_text("console.log('explorer')\n", encoding="utf-8")
    (static_dir / "favicon.svg").write_text(
        '<svg xmlns="http://www.w3.org/2000/svg"></svg>',
        encoding="utf-8",
    )


def test_missing_frontend_is_explicit(tmp_path: Path) -> None:
    response = _client(tmp_path / "missing").get("/")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "frontend_not_built"
    assert "html" not in response.headers["content-type"]
    assert 'id="root"' not in response.text


def test_index_without_assets_is_explicit(tmp_path: Path) -> None:
    (tmp_path / "index.html").write_text('<div id="root"></div>', encoding="utf-8")
    response = _client(tmp_path).get("/")
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "frontend_not_built"


def test_frontend_and_api_routes_stay_distinct(tmp_path: Path) -> None:
    _write_build(tmp_path)
    client = _client(tmp_path)

    page = client.get("/")
    assert page.status_code == 200
    assert "text/html" in page.headers["content-type"]
    assert 'id="root"' in page.text

    asset = client.get("/assets/app.js")
    assert asset.status_code == 200
    assert "console.log" in asset.text
    assert "text/html" not in asset.headers["content-type"]

    icon = client.get("/favicon.svg")
    assert icon.status_code == 200
    assert "image/svg+xml" in icon.headers["content-type"]

    health = client.get("/health")
    assert health.status_code == 200
    assert health.json() == {"status": "ok"}
    assert "JEV" not in health.text

    unknown = client.get("/api/v1/jev/not-a-route")
    assert unknown.status_code == 404
    assert "application/json" in unknown.headers["content-type"]
    body = unknown.json()
    assert "detail" in body or "error" in body
    assert 'id="root"' not in unknown.text

    choice = client.post("/api/v1/jev/choice", json={})
    assert choice.status_code == 422
    assert choice.json()["error"]["code"] == "validation_error"
    assert 'id="root"' not in choice.text

    score = client.post("/api/v1/jev/score", json={})
    assert score.status_code == 422
    noul = client.post("/api/v1/jev/noul", json={})
    assert noul.status_code == 422

    schema = client.get("/openapi.json")
    assert schema.status_code == 200
    paths = schema.json()["paths"]
    assert "/health" in paths
    assert "/api/v1/jev/choice" in paths
    assert "/api/v1/jev/score" in paths
    assert "/api/v1/jev/noul" in paths
