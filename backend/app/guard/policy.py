"""Deterministic policy engine — owns final authorization."""

from __future__ import annotations

from app.config.settings import Settings
from app.guard.models import ActionType, JevDecision, PolicyDecision, PolicyOutcome, ToolMetadata
from app.utils.timing import Timer

# Action types that always require at least confirmation (never auto-execute).
INHERENTLY_SENSITIVE = {
    ActionType.FILESYSTEM_DELETE,
    ActionType.CODE_EXECUTION,
    ActionType.EXTERNAL_SIDE_EFFECT,
    ActionType.CREDENTIAL_OR_SECRET_ACCESS,
    ActionType.PRIVILEGED_ACTION,
    ActionType.NETWORK_ACCESS,
}

# Action types that are blocked unless safe_probability is extremely high
# and risk is low — default policy still blocks high risk.
ALWAYS_BLOCK_IF_HIGH_RISK = True


class PolicyEngine:
    """Maps Jev signals + tool metadata → EXECUTE / CONFIRM / BLOCK."""

    def __init__(self, settings: Settings) -> None:
        self._settings = settings

    def evaluate(
        self,
        jev: JevDecision,
        tool_meta: ToolMetadata | None = None,
    ) -> PolicyDecision:
        with Timer() as timer:
            outcome, reason = self._decide(jev, tool_meta)

        return PolicyDecision(
            outcome=outcome,
            reason=reason,
            policy_version=self._settings.policy_version,
            requires_human_approval=outcome == PolicyOutcome.REQUIRE_CONFIRMATION,
            latency_ms=timer.elapsed_ms,
        )

    def _decide(
        self,
        jev: JevDecision,
        tool_meta: ToolMetadata | None,
    ) -> tuple[PolicyOutcome, str]:
        s = self._settings
        risk = jev.risk_score
        safe = jev.safe_probability
        action = jev.action_type

        destructive = bool(tool_meta and tool_meta.destructive)
        external = bool(tool_meta and tool_meta.external_side_effect)
        tool_requires_confirm = bool(tool_meta and tool_meta.requires_confirmation)

        # Hard blocks
        if risk >= s.block_min_risk:
            return (
                PolicyOutcome.BLOCK,
                f"Risk score {risk:.1f}/5 meets or exceeds block threshold "
                f"({s.block_min_risk}). Automatic execution is not permitted.",
            )

        if safe < s.confirm_min_safe:
            return (
                PolicyOutcome.BLOCK,
                f"Safe-to-execute probability {safe:.2f} is below the minimum "
                f"threshold ({s.confirm_min_safe}). Policy blocks execution.",
            )

        if action == ActionType.CREDENTIAL_OR_SECRET_ACCESS:
            return (
                PolicyOutcome.BLOCK,
                "Credential or secret access is blocked by policy regardless of score.",
            )

        if action == ActionType.PRIVILEGED_ACTION and risk >= 3.0:
            return (
                PolicyOutcome.BLOCK,
                "Privileged actions at moderate-or-higher risk are blocked by policy.",
            )

        if destructive and safe < 0.80:
            return (
                PolicyOutcome.BLOCK,
                "Destructive tool with insufficient safety probability for any execution path.",
            )

        # Auto-execute path
        can_auto = (
            risk <= s.auto_execute_max_risk
            and safe >= s.auto_execute_min_safe
            and action not in INHERENTLY_SENSITIVE
            and not destructive
            and not external
            and not tool_requires_confirm
        )
        if can_auto:
            return (
                PolicyOutcome.EXECUTE,
                f"Risk {risk:.1f}/5 ≤ {s.auto_execute_max_risk} and "
                f"safe probability {safe:.2f} ≥ {s.auto_execute_min_safe}; "
                "action type is not inherently gated.",
            )

        # Confirmation path
        if risk <= s.confirm_max_risk and safe >= s.confirm_min_safe:
            reasons = [
                f"Risk {risk:.1f}/5 within confirmation band (≤ {s.confirm_max_risk})",
                f"safe probability {safe:.2f} ≥ {s.confirm_min_safe}",
            ]
            if action in INHERENTLY_SENSITIVE:
                reasons.append(f"action type `{action.value}` requires human review")
            if destructive:
                reasons.append("tool is marked destructive")
            if external:
                reasons.append("tool has external side effects")
            return (
                PolicyOutcome.REQUIRE_CONFIRMATION,
                "; ".join(reasons) + ".",
            )

        return (
            PolicyOutcome.BLOCK,
            "No policy rule permitted execution or confirmation for this combination "
            f"of risk ({risk:.1f}), safety ({safe:.2f}), and action type ({action.value}).",
        )
