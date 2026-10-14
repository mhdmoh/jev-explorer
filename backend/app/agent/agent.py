"""Lightweight agent that proposes tool calls — never executes tools."""

from __future__ import annotations

from app.agent.scenarios import propose_from_request
from app.guard.models import ToolCall
from app.utils.timing import Timer


class Agent:
    """Deterministic scenario agent (LLM optional later; never bypasses AgentGuard)."""

    def propose(self, user_request: str) -> tuple[ToolCall, float]:
        with Timer() as timer:
            call = propose_from_request(user_request)
        return call, timer.elapsed_ms
