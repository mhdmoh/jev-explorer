from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from app.guard.models import ActionType, ToolMetadata
from app.tools._sandbox import SandboxError, resolve_in_workspace
from app.tools.base import Tool


class CreateNoteTool(Tool):
    def __init__(self, workspace: Path) -> None:
        self._workspace = workspace

    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="create_note",
            description="Create a note inside the demo workspace notes folder.",
            category=ActionType.LOCAL_WRITE,
            reversible=True,
            external_side_effect=False,
            destructive=False,
            requires_confirmation=True,
        )

    def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        content = str(arguments.get("content") or "").strip()
        if not content:
            return {"ok": False, "error": "content is required"}
        name = str(arguments.get("filename") or f"note-{datetime.now(UTC).strftime('%H%M%S')}.txt")
        rel = f"notes/{Path(name).name}"
        try:
            target = resolve_in_workspace(self._workspace, rel)
        except SandboxError as exc:
            return {"ok": False, "error": str(exc)}
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content + "\n", encoding="utf-8")
        return {"ok": True, "path": rel, "bytes": target.stat().st_size}
