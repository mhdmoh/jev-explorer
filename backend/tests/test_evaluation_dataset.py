"""Sanity checks for the evaluation dataset."""

from __future__ import annotations

import json
from pathlib import Path

DATASET = Path(__file__).parent / "evaluation" / "scenarios.json"


def test_evaluation_dataset_shape() -> None:
    data = json.loads(DATASET.read_text(encoding="utf-8"))
    scenarios = data["scenarios"]
    assert len(scenarios) >= 30
    assert data["metric_focus"] == "false_allow_rate"

    required = {
        "id",
        "category",
        "user_request",
        "proposed_tool",
        "arguments",
        "expected_risk_range",
        "expected_policy",
        "rationale",
    }
    policies = {"execute", "require_confirmation", "block"}
    for row in scenarios:
        assert required <= set(row)
        assert row["expected_policy"] in policies
        lo, hi = row["expected_risk_range"]
        assert 1.0 <= lo <= hi <= 5.0
