"""Decision endpoints. No live Jev calls."""

from __future__ import annotations

import json
from collections.abc import Callable

import httpx
import pytest
from app.api.deps import get_jev_client
from app.config.settings import Settings, clear_settings_cache
from app.execution.executor import ToolExecutor
from app.guard.policy import PolicyEngine
from app.jev.client import JevClient
from app.main import app, create_app
from fastapi.testclient import TestClient

API_KEY = "jv_live_test_secret_value"
CHOICE_URL = "/api/v1/jev/choice"
SCORE_URL = "/api/v1/jev/score"
NOUL_URL = "/api/v1/jev/noul"


def _settings(**overrides: object) -> Settings:
    base: dict[str, object] = {
        "_env_file": None,
        "JEV_API_KEY": API_KEY,
        "JEV_MODEL": "jev-1.13.0",
        "JEV_BASE_URL": "https://jevtypesafeai.com/api/v1/decide",
        "RATE_LIMIT_ENABLED": False,
    }
    base.update(overrides)
    return Settings(**base)  # type: ignore[arg-type]


def _install(
    handler: Callable[[httpx.Request], httpx.Response], **overrides: object
) -> JevClient:
    settings = _settings(**overrides)
    http = httpx.Client(transport=httpx.MockTransport(handler))
    client = JevClient(settings, client=http)
    app.dependency_overrides[get_jev_client] = lambda: client
    return client


def _json_response(payload: dict[str, object], status: int = 200) -> httpx.Response:
    return httpx.Response(status, json=payload)


@pytest.fixture(autouse=True)
def _clear_overrides() -> None:
    app.dependency_overrides.clear()
    yield
    app.dependency_overrides.clear()


def test_app_starts_and_health_works_without_jev_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("JEV_API_KEY", "")
    clear_settings_cache()
    try:
        fresh = create_app()
        response = TestClient(fresh).get("/health")
    finally:
        clear_settings_cache()
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


def test_openapi_lists_decision_endpoints() -> None:
    schema = TestClient(app).get("/openapi.json").json()
    paths = schema["paths"]
    for path in (CHOICE_URL, SCORE_URL, NOUL_URL):
        assert path in paths
        operation = paths[path]["post"]
        assert "requestBody" in operation
        assert "200" in operation["responses"]
    component_names = schema["components"]["schemas"]
    expected = (
        "ChoiceRequest",
        "ChoiceResponse",
        "ScoreRequest",
        "ScoreResponse",
        "NoulRequest",
        "NoulResponse",
    )
    for name in expected:
        assert name in component_names


def test_choice_returns_selected_option_and_metadata(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["url"] = str(request.url)
        seen["auth"] = request.headers["authorization"]
        seen["body"] = json.loads(request.content.decode())
        return _json_response(
            {
                "model": "jev-1.13.0",
                "answers": {
                    "result": {
                        "type": "choice",
                        "choice": "billing",
                        "confidence": 0.99,
                        "probabilities": {"billing": 0.99, "bug": 0.01},
                    }
                },
                "usage": {
                    "input_tokens": 62,
                    "cost_usd": 0.000026,
                    "credits_remaining_usd": 4.999974,
                },
            }
        )

    _install(handler)
    calls = {"policy": 0, "tool": 0}

    def reject_policy(*_args: object, **_kwargs: object) -> None:
        calls["policy"] += 1

    def reject_tool(*_args: object, **_kwargs: object) -> None:
        calls["tool"] += 1

    monkeypatch.setattr(PolicyEngine, "evaluate", reject_policy)
    monkeypatch.setattr(ToolExecutor, "run", reject_tool)
    response = TestClient(app).post(
        CHOICE_URL,
        json={
            "state": "Customer was charged twice.",
            "instructions": "Where should this go?",
            "criteria": {"billing": "money", "bug": "broken"},
        },
    )
    assert response.status_code == 200
    body = response.json()
    assert body["type"] == "choice"
    assert body["choice"] == "billing"
    assert body["confidence"] == 0.99
    assert body["probabilities"] == {"billing": 0.99, "bug": 0.01}
    assert body["usage"]["cost_usd"] == 0.000026
    assert body["usage"]["credits_remaining_usd"] == 4.999974
    assert "outcome" not in body
    assert API_KEY not in response.text
    assert seen["auth"] == f"Bearer {API_KEY}"
    assert seen["url"] == "https://jevtypesafeai.com/api/v1/decide"
    upstream = seen["body"]
    assert isinstance(upstream, dict)
    assert upstream["questions"] == {
        "result": {
            "type": "choice",
            "instructions": "Where should this go?",
            "criteria": {"billing": "money", "bug": "broken"},
        }
    }
    assert calls == {"policy": 0, "tool": 0}


def test_choice_preserves_object_state_and_explicit_model() -> None:
    seen: dict[str, object] = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["body"] = json.loads(request.content.decode())
        return _json_response(
            {
                "model": "jev-1.13.0",
                "answers": {
                    "result": {
                        "type": "choice",
                        "choice": "bug",
                        "confidence": 1,
                        "probabilities": {"bug": 1, "billing": 0},
                    }
                },
            }
        )

    _install(handler)
    response = TestClient(app).post(
        CHOICE_URL,
        json={
            "state": {"ticket": "dashboard 500"},
            "instructions": "Route this ticket.",
            "criteria": {"billing": "money", "bug": "broken"},
            "model": "jev-1.13.0",
        },
    )
    assert response.status_code == 200
    assert response.json()["choice"] == "bug"
    upstream = seen["body"]
    assert isinstance(upstream, dict)
    assert upstream["state"] == {"ticket": "dashboard 500"}
    assert upstream["model"] == "jev-1.13.0"


def test_choice_rejects_unknown_selection() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return _json_response(
            {
                "model": "jev-1.13.0",
                "answers": {
                    "result": {
                        "type": "choice",
                        "choice": "other",
                        "confidence": 0.4,
                        "probabilities": {"other": 1},
                    }
                },
            }
        )

    _install(handler)
    response = TestClient(app).post(CHOICE_URL, json=_choice_body())
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "jev_invalid_response"
    assert API_KEY not in response.text


@pytest.mark.parametrize(
    "payload",
    [
        {},
        {"state": "x", "instructions": "pick", "criteria": {}},
        {"state": "x", "instructions": "", "criteria": {"a": "one"}},
        {"state": 1, "instructions": "pick", "criteria": {"a": "one"}},
        {"state": "x", "instructions": "pick", "criteria": ["a", "b"]},
        {
            "state": "x",
            "instructions": "pick",
            "criteria": {"a": "one"},
            "threshold": 0.5,
        },
    ],
)
def test_choice_rejects_malformed_request_before_upstream(
    payload: dict[str, object],
) -> None:
    calls = {"n": 0}

    def handler(_request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return _json_response({})

    _install(handler)
    response = TestClient(app).post(CHOICE_URL, json=payload)
    assert response.status_code == 422
    assert response.json()["error"]["code"] == "validation_error"
    assert calls["n"] == 0
    assert API_KEY not in response.text


def test_choice_criteria_bounds() -> None:
    too_many = {f"opt-{index}": f"option {index}" for index in range(256)}
    _install(lambda _request: _json_response({}))
    response = TestClient(app).post(
        CHOICE_URL,
        json={"state": "x", "instructions": "pick", "criteria": too_many},
    )
    assert response.status_code == 422


def test_score_preserves_fractional_index_and_legend() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return _json_response(
            {
                "model": "jev-1.13.0",
                "answers": {
                    "result": {
                        "type": "score",
                        "score": 2.97,
                        "confidence": 1.0,
                        "legend": {"0": "routine", "3": "critical, about to churn"},
                        "probabilities": {"0": 0.0, "3": 1.0},
                    }
                },
                "usage": {"input_tokens": 434, "output_tokens": 75},
            }
        )

    _install(handler)
    response = TestClient(app).post(SCORE_URL, json=_score_body())
    assert response.status_code == 200
    body = response.json()
    assert body["score"] == 2.97
    assert body["legend"] == {"0": "routine", "3": "critical, about to churn"}
    assert body["probabilities"] == {"0": 0.0, "3": 1.0}
    assert body["usage"]["output_tokens"] == 75
    assert "execute" not in body
    assert API_KEY not in response.text


def test_score_does_not_clamp_out_of_range_index() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return _json_response(
            {
                "model": "jev-1.13.0",
                "answers": {
                    "result": {
                        "type": "score",
                        "score": 10.5,
                        "probabilities": {"0": 1},
                    }
                },
            }
        )

    _install(handler)
    response = TestClient(app).post(SCORE_URL, json=_score_body())
    assert response.status_code == 200
    assert response.json()["score"] == 10.5
    assert response.json()["confidence"] is None


@pytest.mark.parametrize("length", [2, 10])
def test_score_accepts_documented_criteria_lengths(length: int) -> None:
    def handler(request: httpx.Request) -> httpx.Response:
        body = json.loads(request.content.decode())
        assert len(body["questions"]["result"]["criteria"]) == length
        return _json_response(
            {
                "model": "jev-1.13.0",
                "answers": {
                    "result": {
                        "type": "score",
                        "score": 0,
                        "probabilities": {"0": 1},
                    }
                },
            }
        )

    _install(handler)
    criteria = [f"level {index}" for index in range(length)]
    response = TestClient(app).post(
        SCORE_URL,
        json={"state": ["note"], "instructions": "How urgent?", "criteria": criteria},
    )
    assert response.status_code == 200
    assert response.json()["score"] == 0


@pytest.mark.parametrize("length", [1, 11])
def test_score_rejects_criteria_outside_documented_bounds(length: int) -> None:
    calls = {"n": 0}

    def handler(_request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return _json_response({})

    _install(handler)
    criteria = [f"level {index}" for index in range(length)]
    response = TestClient(app).post(
        SCORE_URL,
        json={"state": "x", "instructions": "How urgent?", "criteria": criteria},
    )
    assert response.status_code == 422
    assert calls["n"] == 0


def test_noul_preserves_probability_boundaries() -> None:
    values = iter((0, 1))

    def handler(_request: httpx.Request) -> httpx.Response:
        return _json_response(
            {
                "model": "jev-1.13.0",
                "answers": {"result": {"type": "noul", "noul": next(values)}},
            }
        )

    _install(handler)
    client = TestClient(app)
    low = client.post(NOUL_URL, json=_noul_body())
    high = client.post(NOUL_URL, json=_noul_body())
    assert low.status_code == 200
    assert high.status_code == 200
    assert low.json()["noul"] == 0
    assert high.json()["noul"] == 1
    assert low.json()["type"] == "noul"
    assert "approved" not in low.json()


@pytest.mark.parametrize("noul", [-0.01, 1.01, True, "yes"])
def test_noul_rejects_values_outside_the_contract(noul: object) -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return _json_response(
            {
                "model": "jev-1.13.0",
                "answers": {"result": {"type": "noul", "noul": noul}},
            }
        )

    _install(handler)
    response = TestClient(app).post(NOUL_URL, json=_noul_body())
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "jev_invalid_response"


def test_noul_rejects_malformed_request_before_upstream() -> None:
    calls = {"n": 0}

    def handler(_request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return _json_response({})

    _install(handler)
    response = TestClient(app).post(
        NOUL_URL,
        json={"state": "x", "criteria": {"a": "b"}},
    )
    assert response.status_code == 422
    assert calls["n"] == 0


def test_missing_api_key_returns_503_without_calling_jev() -> None:
    calls = {"n": 0}

    def handler(_request: httpx.Request) -> httpx.Response:
        calls["n"] += 1
        return _json_response({})

    _install(handler, JEV_API_KEY="")
    response = TestClient(app).post(NOUL_URL, json=_noul_body())
    assert response.status_code == 503
    assert response.json()["error"]["code"] == "jev_not_configured"
    assert calls["n"] == 0
    assert "jv_live" not in response.text


def test_upstream_http_error_is_502() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(401, json={"error": "invalid key"})

    _install(handler)
    response = TestClient(app).post(NOUL_URL, json=_noul_body())
    assert response.status_code == 502
    body = response.json()
    assert body["error"]["code"] == "jev_upstream_error"
    assert "401" in body["error"]["message"]
    assert API_KEY not in response.text
    assert "Traceback" not in response.text


def test_upstream_timeout_is_504() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.TimeoutException("timed out")

    _install(handler)
    response = TestClient(app).post(SCORE_URL, json=_score_body())
    assert response.status_code == 504
    assert response.json()["error"]["code"] == "jev_timeout"


def test_network_failure_is_502() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        raise httpx.ConnectError("connection refused")

    _install(handler)
    response = TestClient(app).post(CHOICE_URL, json=_choice_body())
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "jev_network_error"
    assert API_KEY not in response.text


def test_malformed_upstream_json_is_502() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return httpx.Response(200, content=b"not-json")

    _install(handler)
    response = TestClient(app).post(NOUL_URL, json=_noul_body())
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "jev_invalid_response"


def test_unexpected_upstream_shape_is_502() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return _json_response({"model": "jev-1.13.0", "answers": {}})

    _install(handler)
    response = TestClient(app).post(NOUL_URL, json=_noul_body())
    assert response.status_code == 502
    assert response.json()["error"]["code"] == "jev_invalid_response"


def test_unexpected_application_error_hides_internals() -> None:
    def boom() -> None:
        raise RuntimeError(f"leaked {API_KEY}")

    app.dependency_overrides[get_jev_client] = boom
    response = TestClient(app, raise_server_exceptions=False).post(
        NOUL_URL, json=_noul_body()
    )
    assert response.status_code == 500
    assert response.json()["error"]["code"] == "internal_error"
    assert API_KEY not in response.text
    assert "Traceback" not in response.text
    assert "RuntimeError" not in response.text


def test_decision_route_keeps_local_cors() -> None:
    def handler(_request: httpx.Request) -> httpx.Response:
        return _json_response(
            {
                "model": "jev-1.13.0",
                "answers": {"result": {"type": "noul", "noul": 0.94}},
            }
        )

    _install(handler)
    client = TestClient(app)
    allowed = client.post(
        NOUL_URL,
        json=_noul_body(),
        headers={"Origin": "http://localhost:5173"},
    )
    rejected = client.post(
        NOUL_URL,
        json=_noul_body(),
        headers={"Origin": "https://evil.example"},
    )
    assert allowed.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert "access-control-allow-origin" not in rejected.headers


def _choice_body() -> dict[str, object]:
    return {
        "state": "Customer was charged twice.",
        "instructions": "Where should this go?",
        "criteria": {"billing": "money", "bug": "broken"},
    }


def _score_body() -> dict[str, object]:
    return {
        "state": "Nobody replied for 3 days.",
        "instructions": "How urgent is this?",
        "criteria": ["routine", "today", "urgent", "critical"],
    }


def _noul_body() -> dict[str, object]:
    return {
        "state": "Delete the production database.",
        "instructions": "Escalate to a human immediately?",
    }
