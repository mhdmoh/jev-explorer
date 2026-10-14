"""Policy engine unit tests."""

from __future__ import annotations

from app.config.settings import Settings
from app.guard.models import ActionType, JevDecision, PolicyOutcome, ToolMetadata
from app.guard.policy import PolicyEngine


def _settings(**kwargs: object) -> Settings:
    base = {"_env_file": None, "JEV_API_KEY": ""}
    base.update(kwargs)
    return Settings(**base)


def _jev(
    *,
    action: ActionType = ActionType.READ_ONLY,
    risk: float = 1.0,
    safe: float = 0.95,
) -> JevDecision:
    return JevDecision(
        action_type=action,
        risk_score=risk,
        safe_probability=safe,
        model="test",
    )


def test_low_risk_high_safety_executes() -> None:
    engine = PolicyEngine(_settings())
    decision = engine.evaluate(_jev(risk=1.0, safe=0.97))
    assert decision.outcome == PolicyOutcome.EXECUTE


def test_moderate_risk_requires_confirmation() -> None:
    engine = PolicyEngine(_settings())
    meta = ToolMetadata(
        name="create_note",
        description="x",
        category=ActionType.LOCAL_WRITE,
        reversible=True,
        external_side_effect=False,
        destructive=False,
        requires_confirmation=True,
    )
    decision = engine.evaluate(_jev(action=ActionType.LOCAL_WRITE, risk=2.5, safe=0.75), meta)
    assert decision.outcome == PolicyOutcome.REQUIRE_CONFIRMATION


def test_high_risk_blocks() -> None:
    engine = PolicyEngine(_settings())
    decision = engine.evaluate(_jev(action=ActionType.FILESYSTEM_DELETE, risk=4.5, safe=0.20))
    assert decision.outcome == PolicyOutcome.BLOCK


def test_destructive_low_safety_blocks() -> None:
    engine = PolicyEngine(_settings())
    meta = ToolMetadata(
        name="delete_demo_file",
        description="x",
        category=ActionType.FILESYSTEM_DELETE,
        reversible=False,
        external_side_effect=False,
        destructive=True,
    )
    decision = engine.evaluate(
        _jev(action=ActionType.FILESYSTEM_DELETE, risk=3.5, safe=0.55),
        meta,
    )
    assert decision.outcome == PolicyOutcome.BLOCK


def test_credential_access_always_blocked() -> None:
    engine = PolicyEngine(_settings())
    decision = engine.evaluate(
        _jev(action=ActionType.CREDENTIAL_OR_SECRET_ACCESS, risk=2.0, safe=0.99)
    )
    assert decision.outcome == PolicyOutcome.BLOCK
