from __future__ import annotations

from pathlib import Path
from typing import Any

from app.guard.models import ActionType, ToolMetadata
from app.tools.base import Tool


class ListFilesTool(Tool):
    def __init__(self, workspace: Path) -> None:
        self._workspace = workspace

    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="list_files",
            description="List files in the demo workspace.",
            category=ActionType.READ_ONLY,
            reversible=True,
            external_side_effect=False,
            destructive=False,
        )

    def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        entries = sorted(
            str(p.relative_to(self._workspace)) for p in self._workspace.rglob("*") if p.is_file()
        )
        return {"ok": True, "files": entries}
