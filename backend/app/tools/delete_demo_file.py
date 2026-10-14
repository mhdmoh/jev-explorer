from __future__ import annotations

from pathlib import Path
from typing import Any

from app.guard.models import ActionType, ToolMetadata
from app.tools._sandbox import SandboxError, resolve_in_workspace
from app.tools.base import Tool


class DeleteDemoFileTool(Tool):
    def __init__(self, workspace: Path) -> None:
        self._workspace = workspace

    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="delete_demo_file",
            description="Delete a file inside the demo workspace only.",
            category=ActionType.FILESYSTEM_DELETE,
            reversible=False,
            external_side_effect=False,
            destructive=True,
            requires_confirmation=True,
        )

    def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        path = str(arguments.get("path") or "old-report.pdf")
        try:
            target = resolve_in_workspace(self._workspace, path)
        except SandboxError as exc:
            return {"ok": False, "error": str(exc)}
        if not target.exists():
            return {"ok": False, "error": f"File not found: {path}"}
        if not target.is_file():
            return {"ok": False, "error": "Only files can be deleted in the demo"}
        target.unlink()
        return {"ok": True, "deleted": path}
