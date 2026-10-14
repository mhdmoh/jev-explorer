"""Shared domain models for AgentGuard."""

from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ActionType(StrEnum):
    READ_ONLY = "read_only"
    LOCAL_WRITE = "local_write"
    FILESYSTEM_DELETE = "filesystem_delete"
    CODE_EXECUTION = "code_execution"
    EXTERNAL_SIDE_EFFECT = "external_side_effect"
    CREDENTIAL_OR_SECRET_ACCESS = "credential_or_secret_access"
    DATA_MODIFICATION = "data_modification"
    NETWORK_ACCESS = "network_access"
    PRIVILEGED_ACTION = "privileged_action"


class PolicyOutcome(StrEnum):
    EXECUTE = "execute"
    REQUIRE_CONFIRMATION = "require_confirmation"
    BLOCK = "block"


class ToolCall(BaseModel):
    """Structured tool-call proposal from the agent."""

    tool_name: str
    arguments: dict[str, Any] = Field(default_factory=dict)
    agent_reasoning_summary: str = ""
    agent_goal: str = ""


class ToolMetadata(BaseModel):
    name: str
    description: str
    category: ActionType
    reversible: bool
    external_side_effect: bool
    destructive: bool
    requires_confirmation: bool = False


class JevDecision(BaseModel):
    """Typed decision signals from Jev (not final authorization)."""

    action_type: ActionType
    action_type_confidence: float | None = None
    action_type_probabilities: dict[str, float] | None = None
    risk_score: float
    risk_confidence: float | None = None
    risk_probabilities: dict[str, float] | None = None
    safe_probability: float
    model: str
    demo_mode: bool = False
    latency_ms: float | None = None


class PolicyDecision(BaseModel):
    outcome: PolicyOutcome
    reason: str
    policy_version: str
    requires_human_approval: bool
    latency_ms: float | None = None


class AuditEvent(BaseModel):
    timestamp: datetime = Field(default_factory=lambda: datetime.now(UTC))
    stage: str
    event: str
    metadata: dict[str, Any] = Field(default_factory=dict)
    duration_ms: float | None = None


class ExecutionResult(BaseModel):
    executed: bool
    success: bool
    message: str
    output: Any = None
    latency_ms: float | None = None


class AgentRun(BaseModel):
    """Full lifecycle of one agent request through AgentGuard."""

    run_id: str
    user_request: str
    tool_call: ToolCall | None = None
    tool_metadata: ToolMetadata | None = None
    jev_decision: JevDecision | None = None
    policy_decision: PolicyDecision | None = None
    human_decision: str | None = None  # approved | rejected | None
    execution_result: ExecutionResult | None = None
    events: list[AuditEvent] = Field(default_factory=list)
    error: str | None = None

    agent_latency_ms: float | None = None
    jev_latency_ms: float | None = None
    policy_latency_ms: float | None = None
    execution_latency_ms: float | None = None
    total_latency_ms: float | None = None
    demo_mode: bool = False
