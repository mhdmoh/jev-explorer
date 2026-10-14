from __future__ import annotations

from typing import Any

from app.guard.models import ActionType, ToolMetadata
from app.tools.base import Tool

ALLOWED_TASKS = {
    "cleanup_temp": "Cleared simulated temporary artifacts in the demo sandbox.",
    "health_check": "Ran simulated health check — all demo services healthy.",
}


class ExecuteDemoTaskTool(Tool):
    """Represents code execution without running arbitrary user input."""

    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="execute_demo_task",
            description="Run a predefined safe demonstration task (not arbitrary code).",
            category=ActionType.CODE_EXECUTION,
            reversible=False,
            external_side_effect=False,
            destructive=False,
            requires_confirmation=True,
        )

    def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        task = str(arguments.get("task") or "").strip()
        if task not in ALLOWED_TASKS:
            return {
                "ok": False,
                "error": f"Unknown demo task. Allowed: {sorted(ALLOWED_TASKS)}",
            }
        return {"ok": True, "task": task, "result": ALLOWED_TASKS[task], "simulated": True}
