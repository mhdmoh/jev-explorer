"""Thin HTTP adapters for one Jev primitive at a time.

These routes return Jev's typed signal. They do not apply Jev Explorer policy
and they do not execute tools.
"""

from __future__ import annotations

import uuid
from collections.abc import Callable

from fastapi import APIRouter, Request
from pydantic import ValidationError

from app.api.deps import JevClientDep, SettingsDep, caller_identity
from app.api.errors import raise_for_jev
from app.config.settings import ConfigError
from app.jev.answers import parse_choice_answer, parse_noul_answer, parse_score_answer
from app.jev.client import JevClientError
from app.schemas.decisions import (
    ChoiceRequest,
    ChoiceResponse,
    ErrorResponse,
    NoulRequest,
    NoulResponse,
    ScoreRequest,
    ScoreResponse,
)

router = APIRouter(prefix="/api/v1/jev", tags=["jev"])

_ERRORS = {
    422: {"model": ErrorResponse},
    429: {"model": ErrorResponse},
    502: {"model": ErrorResponse},
    503: {"model": ErrorResponse},
    504: {"model": ErrorResponse},
}


@router.post(
    "/choice",
    response_model=ChoiceResponse,
    responses=_ERRORS,
    summary="Ask Jev to select one option",
)
def choose(
    body: ChoiceRequest,
    request: Request,
    settings: SettingsDep,
    client: JevClientDep,
) -> ChoiceResponse:
    """Select one supplied option. The result is a signal, not permission to act."""
    anonymous_id, client_ip = caller_identity(request, settings)

    def build() -> ChoiceResponse:
        payload = client.choice(
            state=body.state,
            instructions=body.instructions,
            criteria=body.criteria,
            model=body.model,
            run_id=_run_id(),
            client_ip=client_ip,
            anonymous_id=anonymous_id,
        )
        parsed = parse_choice_answer(payload, criteria_keys=set(body.criteria))
        return ChoiceResponse.model_validate(parsed)

    return _result(build, secret=settings.jev_api_key)


@router.post(
    "/score",
    response_model=ScoreResponse,
    responses=_ERRORS,
    summary="Ask Jev to score an ordered scale",
)
def score(
    body: ScoreRequest,
    request: Request,
    settings: SettingsDep,
    client: JevClientDep,
) -> ScoreResponse:
    """Return Jev's score index unchanged. Jev Explorer does not clamp or authorize it."""
    anonymous_id, client_ip = caller_identity(request, settings)

    def build() -> ScoreResponse:
        payload = client.score(
            state=body.state,
            instructions=body.instructions,
            criteria=body.criteria,
            model=body.model,
            run_id=_run_id(),
            client_ip=client_ip,
            anonymous_id=anonymous_id,
        )
        return ScoreResponse.model_validate(parse_score_answer(payload))

    return _result(build, secret=settings.jev_api_key)


@router.post(
    "/noul",
    response_model=NoulResponse,
    responses=_ERRORS,
    summary="Ask Jev for a calibrated yes/no probability",
)
def noul(
    body: NoulRequest,
    request: Request,
    settings: SettingsDep,
    client: JevClientDep,
) -> NoulResponse:
    """Return Jev's 0–1 probability. This route does not apply a yes/no threshold."""
    anonymous_id, client_ip = caller_identity(request, settings)

    def build() -> NoulResponse:
        payload = client.noul(
            state=body.state,
            instructions=body.instructions,
            model=body.model,
            run_id=_run_id(),
            client_ip=client_ip,
            anonymous_id=anonymous_id,
        )
        return NoulResponse.model_validate(parse_noul_answer(payload))

    return _result(build, secret=settings.jev_api_key)


def _result[T](build: Callable[[], T], *, secret: str) -> T:
    try:
        return build()
    except ValidationError:
        raise_for_jev(
            JevClientError(
                "Jev returned an unexpected response", code="invalid_response"
            ),
            secret=secret,
        )
    except (ConfigError, JevClientError) as exc:
        raise_for_jev(exc, secret=secret)


def _run_id() -> str:
    return uuid.uuid4().hex[:12]
