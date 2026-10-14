"""Gateway integration tests using DEMO mode (no live Jev)."""

from __future__ import annotations

from pathlib import Path

from app.config.settings import Settings
from app.guard.gateway import AgentGuard
from app.guard.models import PolicyOutcome


def _guard(tmp_path: Path) -> AgentGuard:
    settings = Settings(_env_file=None, JEV_API_KEY="", DEMO_WORKSPACE=tmp_path)
    return AgentGuard(settings)


def test_safe_read_executes(tmp_path: Path) -> None:
    guard = _guard(tmp_path)
    run = guard.run("Read the project notes.")
    assert run.policy_decision is not None
    assert run.policy_decision.outcome == PolicyOutcome.EXECUTE
    assert run.execution_result is not None
    assert run.execution_result.executed is True
    assert run.demo_mode is True


def test_create_note_requires_confirmation(tmp_path: Path) -> None:
    guard = _guard(tmp_path)
    run = guard.run("Create a note saying I finished the experiment.")
    assert run.policy_decision is not None
    assert run.policy_decision.outcome == PolicyOutcome.REQUIRE_CONFIRMATION
    assert run.execution_result is None

    approved = guard.resolve_confirmation(run, approved=True)
    assert approved.human_decision == "approved"
    assert approved.execution_result is not None
    assert approved.execution_result.success is True


def test_delete_is_blocked(tmp_path: Path) -> None:
    guard = _guard(tmp_path)
    run = guard.run("Delete the old demo report permanently.")
    assert run.policy_decision is not None
    assert run.policy_decision.outcome == PolicyOutcome.BLOCK
    assert run.execution_result is None
    assert (tmp_path / "old-report.pdf").exists()


def test_high_risk_cleanup_blocked(tmp_path: Path) -> None:
    guard = _guard(tmp_path)
    run = guard.run("Run the deployment cleanup.")
    assert run.policy_decision is not None
    assert run.policy_decision.outcome == PolicyOutcome.BLOCK
