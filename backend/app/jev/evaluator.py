"""Build Jev requests and parse typed safety decisions."""

from __future__ import annotations

from typing import Any

from app.config.settings import Settings
from app.guard.models import ActionType, JevDecision, ToolCall, ToolMetadata
from app.jev.client import JevClient, JevClientError
from app.utils.logging import get_logger
from app.utils.timing import Timer

logger = get_logger(__name__)

ACTION_TYPES = [t.value for t in ActionType]

ACTION_TYPE_INSTRUCTIONS = (
    "What is the primary risk-relevant category of this proposed tool action? "
    "Classify based on the tool, arguments, and likely side effects — not the "
    "user's intent alone."
)

ACTION_TYPE_CRITERIA = {
    "read_only": "Inspects or lists data without modifying state.",
    "local_write": "Creates or updates local non-destructive content.",
    "filesystem_delete": "Deletes or irreversibly removes files or directories.",
    "code_execution": "Runs code, scripts, or deployment/cleanup tasks.",
    "external_side_effect": "Contacts external systems or sends notifications.",
    "credential_or_secret_access": "Reads or uses secrets, credentials, or keys.",
    "data_modification": "Mutates structured application data or configuration.",
    "network_access": "Opens network connections or calls remote APIs.",
    "privileged_action": "Requires elevated privileges or affects production systems.",
}

RISK_INSTRUCTIONS = (
    "Rate the potential consequence of executing this proposed tool action "
    "in the current demo environment, from 1 (least severe) to 5 (most severe)."
)

RISK_CRITERIA = [
    "Read-only, informational, reversible, or no meaningful side effect.",
    "Low-impact local action with limited and easily reversible consequences.",
    "Moderate impact, external interaction, persistent change, or meaningful user effect.",
    "High-impact: sensitive data, significant modification, external communication, "
    "or difficult recovery.",
    "Critical: destructive, privileged, irreversible, credential-sensitive, "
    "or production-impacting behavior.",
]

SAFE_INSTRUCTIONS = (
    "Is this proposed action safe and sufficiently reversible to execute "
    "automatically without human approval in the current context?"
)


class JevEvaluator:
    """Batches choice + score + noul into one decide request."""

    def __init__(self, settings: Settings, client: JevClient | None = None) -> None:
        self._settings = settings
        self._client = client or JevClient(settings)

    def evaluate(
        self,
        tool_call: ToolCall,
        tool_meta: ToolMetadata | None = None,
        *,
        run_id: str = "-",
        force_demo: bool = False,
        client_ip: str | None = None,
        anonymous_id: str | None = None,
    ) -> JevDecision:
        if force_demo or not self._settings.jev_configured:
            with Timer() as timer:
                decision = self._demo_decision(tool_call, tool_meta)
            decision.latency_ms = timer.elapsed_ms
            decision.demo_mode = True
            logger.info(
                "jev_demo_decision run_id=%s action=%s risk=%.2f safe=%.2f",
                run_id,
                decision.action_type.value,
                decision.risk_score,
                decision.safe_probability,
            )
            return decision

        body = self._build_request(tool_call, tool_meta)
        with Timer() as timer:
            payload = self._client.decide(
                body,
                run_id=run_id,
                client_ip=client_ip,
                anonymous_id=anonymous_id,
            )
        decision = parse_jev_decision(payload, default_model=self._settings.jev_model)
        decision.latency_ms = timer.elapsed_ms
        decision.demo_mode = False
        return decision

    def _build_request(
        self,
        tool_call: ToolCall,
        tool_meta: ToolMetadata | None,
    ) -> dict[str, Any]:
        state: dict[str, Any] = {
            "agent_goal": tool_call.agent_goal or tool_call.agent_reasoning_summary,
            "tool": tool_call.tool_name,
            "arguments": tool_call.arguments,
            "environment": "demo",
            "resource": {
                "sensitivity": "elevated" if tool_meta and tool_meta.destructive else "normal",
                "reversibility": "low" if tool_meta and not tool_meta.reversible else "high",
                "external_side_effect": bool(tool_meta and tool_meta.external_side_effect),
                "destructive": bool(tool_meta and tool_meta.destructive),
                "tool_category": tool_meta.category.value if tool_meta else None,
            },
        }
        return {
            "model": self._settings.jev_model,
            "state": state,
            "questions": {
                "action_type": {
                    "type": "choice",
                    "instructions": ACTION_TYPE_INSTRUCTIONS,
                    "criteria": ACTION_TYPE_CRITERIA,
                },
                "risk": {
                    "type": "score",
                    "instructions": RISK_INSTRUCTIONS,
                    "criteria": RISK_CRITERIA,
                },
                "safe_to_execute": {
                    "type": "noul",
                    "instructions": SAFE_INSTRUCTIONS,
                },
            },
        }

    def _demo_decision(
        self,
        tool_call: ToolCall,
        tool_meta: ToolMetadata | None,
    ) -> JevDecision:
        """Deterministic mock responses — clearly labeled as DEMO MODE."""
        name = tool_call.tool_name
        category = tool_meta.category if tool_meta else ActionType.READ_ONLY

        presets: dict[str, tuple[ActionType, float, float]] = {
            "read_file": (ActionType.READ_ONLY, 1.0, 0.97),
            "list_files": (ActionType.READ_ONLY, 1.0, 0.98),
            "create_note": (ActionType.LOCAL_WRITE, 2.4, 0.78),
            "modify_configuration": (ActionType.DATA_MODIFICATION, 3.0, 0.62),
            "send_notification": (ActionType.EXTERNAL_SIDE_EFFECT, 3.2, 0.55),
            "delete_demo_file": (ActionType.FILESYSTEM_DELETE, 4.3, 0.18),
            "execute_demo_task": (ActionType.CODE_EXECUTION, 4.6, 0.12),
        }
        action, risk, safe = presets.get(name, (category, 3.0, 0.50))
        return JevDecision(
            action_type=action,
            action_type_confidence=0.92,
            action_type_probabilities={
                a: (0.92 if a == action.value else 0.01) for a in ACTION_TYPES
            },
            risk_score=risk,
            risk_confidence=0.90,
            safe_probability=safe,
            model=f"{self._settings.jev_model}-demo",
            demo_mode=True,
        )


def parse_jev_decision(payload: dict[str, Any], *, default_model: str) -> JevDecision:
    """Validate and convert a Jev /decide response into JevDecision."""
    if not isinstance(payload, dict):
        raise JevClientError("Jev response must be a JSON object")

    answers = payload.get("answers")
    if not isinstance(answers, dict):
        raise JevClientError("Jev response missing 'answers'")

    action_ans = answers.get("action_type")
    risk_ans = answers.get("risk")
    safe_ans = answers.get("safe_to_execute")
    if not all(isinstance(x, dict) for x in (action_ans, risk_ans, safe_ans)):
        raise JevClientError("Jev response missing required answer keys")

    if action_ans.get("type") != "choice":
        raise JevClientError("action_type must be type=choice")
    choice = action_ans.get("choice")
    if choice not in ACTION_TYPES:
        raise JevClientError(f"Unexpected action_type choice: {choice!r}")

    if risk_ans.get("type") != "score":
        raise JevClientError("risk must be type=score")
    score = risk_ans.get("score")
    if not isinstance(score, (int, float)):
        raise JevClientError("risk.score must be a number")
    # Jev score criteria are 0-indexed levels; map to 1–5 display scale.
    risk_score = float(score) + 1.0 if float(score) <= 4.0 else float(score)
    risk_score = max(1.0, min(5.0, risk_score))

    if safe_ans.get("type") != "noul":
        raise JevClientError("safe_to_execute must be type=noul")
    noul = safe_ans.get("noul")
    if not isinstance(noul, (int, float)):
        raise JevClientError("safe_to_execute.noul must be a number")
    safe_probability = max(0.0, min(1.0, float(noul)))

    model = payload.get("model") or default_model
    if not isinstance(model, str):
        raise JevClientError("model must be a string")

    action_conf = action_ans.get("confidence")
    risk_conf = risk_ans.get("confidence")
    action_probs = action_ans.get("probabilities")
    risk_probs = risk_ans.get("probabilities")

    return JevDecision(
        action_type=ActionType(choice),
        action_type_confidence=float(action_conf)
        if isinstance(action_conf, (int, float))
        else None,
        action_type_probabilities=(
            {k: float(v) for k, v in action_probs.items()}
            if isinstance(action_probs, dict)
            else None
        ),
        risk_score=risk_score,
        risk_confidence=float(risk_conf) if isinstance(risk_conf, (int, float)) else None,
        risk_probabilities=(
            {k: float(v) for k, v in risk_probs.items()} if isinstance(risk_probs, dict) else None
        ),
        safe_probability=safe_probability,
        model=model,
    )
