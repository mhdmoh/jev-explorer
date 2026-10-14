from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.guard.models import ActionType, ToolMetadata
from app.tools._sandbox import resolve_in_workspace
from app.tools.base import Tool


class ModifyConfigurationTool(Tool):
    def __init__(self, workspace: Path) -> None:
        self._workspace = workspace
        self._path = workspace / "config.json"
        if not self._path.exists():
            self._path.write_text(
                json.dumps({"mode": "demo", "notifications": False}, indent=2),
                encoding="utf-8",
            )

    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="modify_configuration",
            description="Update a key in the demo configuration object.",
            category=ActionType.DATA_MODIFICATION,
            reversible=True,
            external_side_effect=False,
            destructive=False,
            requires_confirmation=True,
        )

    def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        key = str(arguments.get("key") or "").strip()
        if not key:
            return {"ok": False, "error": "key is required"}
        value = arguments.get("value")
        data = json.loads(self._path.read_text(encoding="utf-8"))
        previous = data.get(key)
        data[key] = value
        # Ensure we stay in workspace
        resolve_in_workspace(self._workspace, "config.json")
        self._path.write_text(json.dumps(data, indent=2), encoding="utf-8")
        return {"ok": True, "key": key, "previous": previous, "value": value}
