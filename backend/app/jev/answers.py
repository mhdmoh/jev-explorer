"""Parse one answer from a Jev /decide payload.

The gateway evaluator interprets scores for policy. These parsers do not.
They keep the upstream values, including a fractional score index.
"""

from __future__ import annotations

from typing import Any

from app.jev.client import QUESTION_KEY, JevClientError


def parse_choice_answer(
    payload: dict[str, Any],
    *,
    criteria_keys: set[str],
) -> dict[str, Any]:
    answer = _require_answer(payload, expected_type="choice")
    choice = answer.get("choice")
    if not isinstance(choice, str) or choice not in criteria_keys:
        raise JevClientError(
            "Jev choice was missing or not one of the supplied options",
            code="invalid_response",
        )
    _require_confidence(answer)
    _require_probabilities(answer)
    return _with_envelope(payload, answer)


def parse_score_answer(payload: dict[str, Any]) -> dict[str, Any]:
    answer = _require_answer(payload, expected_type="score")
    _require_number(answer.get("score"), "score")
    if "confidence" in answer and answer.get("confidence") is not None:
        _require_number(answer.get("confidence"), "confidence")
    _require_probabilities(answer)
    legend = answer.get("legend")
    if legend is not None and not _is_string_map(legend):
        raise JevClientError(
            "Jev score legend must be an object of strings",
            code="invalid_response",
        )
    return _with_envelope(payload, answer)


def parse_noul_answer(payload: dict[str, Any]) -> dict[str, Any]:
    answer = _require_answer(payload, expected_type="noul")
    noul = _require_number(answer.get("noul"), "noul")
    if not 0.0 <= noul <= 1.0:
        raise JevClientError(
            "Jev noul must be a probability from 0 to 1",
            code="invalid_response",
        )
    return _with_envelope(payload, answer)


def _require_answer(payload: dict[str, Any], *, expected_type: str) -> dict[str, Any]:
    if not isinstance(payload.get("model"), str) or not payload["model"].strip():
        raise JevClientError("Jev response missing model", code="invalid_response")
    usage = payload.get("usage")
    if usage is not None and not isinstance(usage, dict):
        raise JevClientError("Jev usage must be an object", code="invalid_response")

    answers = payload.get("answers")
    if not isinstance(answers, dict):
        raise JevClientError("Jev response missing answers", code="invalid_response")
    answer = answers.get(QUESTION_KEY)
    if not isinstance(answer, dict):
        raise JevClientError(
            "Jev response missing the decision answer", code="invalid_response"
        )
    if answer.get("type") != expected_type:
        raise JevClientError(
            f"Jev answer type must be {expected_type}",
            code="invalid_response",
        )
    return answer


def _with_envelope(payload: dict[str, Any], answer: dict[str, Any]) -> dict[str, Any]:
    enriched = dict(answer)
    enriched["model"] = payload["model"]
    if "usage" in payload:
        enriched["usage"] = payload["usage"]
    return enriched


def _require_confidence(answer: dict[str, Any]) -> None:
    _require_number(answer.get("confidence"), "confidence")


def _require_probabilities(answer: dict[str, Any]) -> None:
    probabilities = answer.get("probabilities")
    if not isinstance(probabilities, dict) or not probabilities:
        raise JevClientError(
            "Jev response missing probabilities",
            code="invalid_response",
        )
    for key, value in probabilities.items():
        if not isinstance(key, str):
            raise JevClientError(
                "Jev probabilities keys must be strings",
                code="invalid_response",
            )
        _require_number(value, "probabilities")


def _require_number(value: Any, field: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise JevClientError(
            f"Jev field {field} must be a number", code="invalid_response"
        )
    return float(value)


def _is_string_map(value: Any) -> bool:
    return isinstance(value, dict) and all(
        isinstance(key, str) and isinstance(item, str) for key, item in value.items()
    )
