"""AgentGuard gateway — orchestrates evaluate → policy → (optional) execute."""

from __future__ import annotations

import time
import uuid

from app.agent.agent import Agent
from app.config.settings import Settings
from app.execution.audit import event
from app.execution.executor import ToolExecutor
from app.guard.models import AgentRun, PolicyOutcome
from app.guard.policy import PolicyEngine
from app.jev.client import JevClientError
from app.jev.evaluator import JevEvaluator
from app.tools.registry import ToolRegistry, UnknownToolError
from app.utils.logging import get_logger

logger = get_logger(__name__)


class AgentGuard:
    """
    Safety gateway between agent proposals and tool execution.

    Separation:
      Agent → ToolCall → AgentGuard → JevEvaluator → PolicyEngine → ToolExecutor
    """

    def __init__(
        self,
        settings: Settings,
        *,
        agent: Agent | None = None,
        evaluator: JevEvaluator | None = None,
        policy: PolicyEngine | None = None,
        registry: ToolRegistry | None = None,
        executor: ToolExecutor | None = None,
    ) -> None:
        self._settings = settings
        self._agent = agent or Agent()
        self._evaluator = evaluator or JevEvaluator(settings)
        self._policy = policy or PolicyEngine(settings)
        self._registry = registry or ToolRegistry(settings.demo_workspace)
        self._executor = executor or ToolExecutor(self._registry)

    @property
    def demo_mode(self) -> bool:
        return not self._settings.jev_configured

    @property
    def registry(self) -> ToolRegistry:
        return self._registry

    def run(
        self,
        user_request: str,
        *,
        client_ip: str | None = None,
        anonymous_id: str | None = None,
    ) -> AgentRun:
        """Propose + evaluate + apply policy. Does not execute confirmation-gated tools."""
        run_id = uuid.uuid4().hex[:12]
        started = time.perf_counter()
        run = AgentRun(run_id=run_id, user_request=user_request, demo_mode=self.demo_mode)
        run.events.append(event("agent", "request_received", request_preview=user_request[:120]))

        logger.info(
            "run_started run_id=%s demo_mode=%s client_ip=%s anon=%s",
            run_id,
            self.demo_mode,
            client_ip or "-",
            (anonymous_id or "-")[:8],
        )

        try:
            tool_call, agent_ms = self._agent.propose(user_request)
        except Exception as exc:  # noqa: BLE001
            run.error = f"Agent failed: {exc}"
            run.total_latency_ms = (time.perf_counter() - started) * 1000
            return run

        run.tool_call = tool_call
        run.agent_latency_ms = agent_ms
        run.events.append(
            event(
                "agent",
                "tool_proposed",
                duration_ms=agent_ms,
                tool=tool_call.tool_name,
                arguments=tool_call.arguments,
            )
        )

        try:
            meta = self._registry.get(tool_call.tool_name).metadata
        except UnknownToolError as exc:
            run.error = str(exc)
            run.total_latency_ms = (time.perf_counter() - started) * 1000
            return run

        run.tool_metadata = meta
        run.events.append(event("guard", "arguments_validated", tool=tool_call.tool_name))

        try:
            jev = self._evaluator.evaluate(
                tool_call,
                meta,
                run_id=run_id,
                client_ip=client_ip,
                anonymous_id=anonymous_id,
            )
        except JevClientError as exc:
            run.error = f"Jev evaluation failed: {exc}"
            run.events.append(event("jev", "evaluation_failed", error=str(exc)))
            run.total_latency_ms = (time.perf_counter() - started) * 1000
            logger.error("jev_failed run_id=%s error=%s", run_id, exc)
            return run

        run.jev_decision = jev
        run.jev_latency_ms = jev.latency_ms
        run.demo_mode = jev.demo_mode
        run.events.append(
            event(
                "jev",
                "decision_received",
                duration_ms=jev.latency_ms,
                action_type=jev.action_type.value,
                risk=jev.risk_score,
                safe_probability=jev.safe_probability,
                demo_mode=jev.demo_mode,
            )
        )

        policy = self._policy.evaluate(jev, meta)
        run.policy_decision = policy
        run.policy_latency_ms = policy.latency_ms
        run.events.append(
            event(
                "policy",
                "decision_made",
                duration_ms=policy.latency_ms,
                outcome=policy.outcome.value,
                reason=policy.reason,
            )
        )

        if policy.outcome == PolicyOutcome.EXECUTE:
            result = self._executor.run(tool_call)
            run.execution_result = result
            run.execution_latency_ms = result.latency_ms
            run.events.append(
                event(
                    "tool",
                    "executed" if result.executed else "execution_failed",
                    duration_ms=result.latency_ms,
                    success=result.success,
                    message=result.message,
                )
            )
        elif policy.outcome == PolicyOutcome.BLOCK:
            run.events.append(event("tool", "execution_prevented", reason=policy.reason))
        else:
            run.events.append(event("policy", "awaiting_human_approval"))

        run.total_latency_ms = (time.perf_counter() - started) * 1000
        logger.info(
            "run_completed run_id=%s outcome=%s total_ms=%.1f",
            run_id,
            policy.outcome.value,
            run.total_latency_ms,
        )
        return run

    def resolve_confirmation(self, run: AgentRun, *, approved: bool) -> AgentRun:
        """Continue a confirmation-gated run after human decision."""
        if run.policy_decision is None or run.tool_call is None:
            run.error = "Cannot resolve confirmation: incomplete run state."
            return run
        if run.policy_decision.outcome != PolicyOutcome.REQUIRE_CONFIRMATION:
            run.error = "This run is not awaiting confirmation."
            return run

        run.human_decision = "approved" if approved else "rejected"
        run.events.append(event("human", "approved" if approved else "rejected"))

        if not approved:
            run.events.append(event("tool", "execution_prevented", reason="Human rejected"))
            return run

        result = self._executor.run(run.tool_call)
        run.execution_result = result
        run.execution_latency_ms = result.latency_ms
        run.events.append(
            event(
                "tool",
                "executed" if result.success else "execution_failed",
                duration_ms=result.latency_ms,
                success=result.success,
                message=result.message,
            )
        )
        return run
