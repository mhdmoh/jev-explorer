"""Jev response parsing tests."""

from __future__ import annotations

import pytest
from app.guard.models import ActionType
from app.jev.client import JevClientError
from app.jev.evaluator import parse_jev_decision


def test_parse_valid_batched_response() -> None:
    payload = {
        "model": "jev-1.13.0",
        "answers": {
            "action_type": {
                "type": "choice",
                "choice": "filesystem_delete",
                "confidence": 0.91,
                "probabilities": {"filesystem_delete": 0.91, "read_only": 0.09},
            },
            "risk": {
                "type": "score",
                "score": 3.2,
                "confidence": 0.88,
                "probabilities": {"3": 0.8, "4": 0.2},
            },
            "safe_to_execute": {"type": "noul", "noul": 0.21},
        },
    }
    decision = parse_jev_decision(payload, default_model="jev-1.13.0")
    assert decision.action_type == ActionType.FILESYSTEM_DELETE
    assert decision.risk_score == pytest.approx(4.2)
    assert decision.safe_probability == 0.21
    assert decision.action_type_confidence == 0.91


def test_parse_malformed_missing_answers() -> None:
    with pytest.raises(JevClientError):
        parse_jev_decision({}, default_model="jev-1.13.0")


def test_parse_wrong_choice() -> None:
    payload = {
        "answers": {
            "action_type": {"type": "choice", "choice": "not_a_type"},
            "risk": {"type": "score", "score": 1.0},
            "safe_to_execute": {"type": "noul", "noul": 0.9},
        }
    }
    with pytest.raises(JevClientError):
        parse_jev_decision(payload, default_model="jev-1.13.0")
