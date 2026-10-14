from __future__ import annotations

from pathlib import Path
from typing import Any

from app.guard.models import ActionType, ToolMetadata
from app.tools._sandbox import SandboxError, resolve_in_workspace
from app.tools.base import Tool


class ReadFileTool(Tool):
    def __init__(self, workspace: Path) -> None:
        self._workspace = workspace

    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="read_file",
            description="Read a file from the demo workspace.",
            category=ActionType.READ_ONLY,
            reversible=True,
            external_side_effect=False,
            destructive=False,
        )

    def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        path = str(arguments.get("path") or "project-notes.txt")
        try:
            target = resolve_in_workspace(self._workspace, path)
        except SandboxError as exc:
            return {"ok": False, "error": str(exc)}
        if not target.is_file():
            return {"ok": False, "error": f"File not found: {path}"}
        return {"ok": True, "path": path, "content": target.read_text(encoding="utf-8")}
