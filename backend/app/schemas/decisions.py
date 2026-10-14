"""HTTP models for the Jev choice, score, and noul endpoints.

Field meanings follow the hosted decide contract:
https://www.jevtypesafeai.com/docs
"""

from __future__ import annotations

from typing import Any, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator

MAX_CHOICE_OPTIONS = 255
MIN_SCORE_LEVELS = 2
MAX_SCORE_LEVELS = 10


class ErrorBody(BaseModel):
    code: str
    message: str
    details: list[dict[str, Any]] | None = None


class ErrorResponse(BaseModel):
    error: ErrorBody


class JevUsage(BaseModel):
    """Token and billing metadata. Published examples do not all include the same keys."""

    model_config = ConfigDict(extra="allow")

    input_tokens: int | None = None
    output_tokens: int | None = None
    cost_usd: float | None = None
    credits_remaining_usd: float | None = None


class _DecisionRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    state: str | dict[str, Any] | list[Any] = Field(
        description="Context for the decision. A string, object, or array, matching Jev state.",
    )
    instructions: str = Field(min_length=1, description="What Jev should decide.")
    model: str | None = Field(
        default=None,
        min_length=1,
        description="Optional model id. When omitted, the server sends JEV_MODEL.",
    )


class ChoiceRequest(_DecisionRequest):
    criteria: dict[str, str] = Field(
        description="Up to 255 labelled options. Keys are the selectable values.",
    )

    @field_validator("criteria")
    @classmethod
    def validate_criteria(cls, value: dict[str, str]) -> dict[str, str]:
        if not value:
            raise ValueError("criteria must contain at least one option")
        if len(value) > MAX_CHOICE_OPTIONS:
            raise ValueError(
                f"criteria must contain at most {MAX_CHOICE_OPTIONS} options"
            )
        if any(not key.strip() for key in value):
            raise ValueError("criteria keys must be non-empty")
        if any(not item.strip() for item in value.values()):
            raise ValueError("criteria descriptions must be non-empty")
        return value


class ScoreRequest(_DecisionRequest):
    criteria: list[str] = Field(
        min_length=MIN_SCORE_LEVELS,
        max_length=MAX_SCORE_LEVELS,
        description="Ordered level descriptions, low to high. Length 2–10. Index 0 is the lowest.",
    )

    @field_validator("criteria")
    @classmethod
    def validate_levels(cls, value: list[str]) -> list[str]:
        if any(not item.strip() for item in value):
            raise ValueError("score levels must be non-empty")
        return value


class NoulRequest(_DecisionRequest):
    """A calibrated yes/no. Jev returns a probability, not a boolean."""


class ChoiceResponse(BaseModel):
    """Winning option plus the distribution Jev returned. Not an authorization."""

    model_config = ConfigDict(extra="allow")

    model: str
    type: Literal["choice"]
    choice: str = Field(description="Selected criteria key.")
    confidence: float
    probabilities: dict[str, float]
    usage: JevUsage | None = None


class ScoreResponse(BaseModel):
    """Score index on the supplied criteria. Possibly fractional. Not clamped."""

    model_config = ConfigDict(extra="allow")

    model: str
    type: Literal["score"]
    score: float = Field(
        description="Position on the criteria index, low to high. May be fractional.",
    )
    confidence: float | None = None
    probabilities: dict[str, float] = Field(
        description='Probability mass by criteria index. Keys are decimal strings such as "0".',
    )
    legend: dict[str, str] | None = Field(
        default=None,
        description='Index-to-label map when Jev includes one. Shape is {"0": "lowest label"}.',
    )
    usage: JevUsage | None = None


class NoulResponse(BaseModel):
    """Calibrated probability that the answer is yes. Not a boolean and not a policy threshold."""

    model_config = ConfigDict(extra="allow")

    model: str
    type: Literal["noul"]
    noul: float = Field(
        ge=0.0,
        le=1.0,
        description="Probability from 0 to 1 that the answer is yes.",
    )
    usage: JevUsage | None = None
