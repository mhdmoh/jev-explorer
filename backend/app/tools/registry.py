"""Controlled tool registry — no arbitrary shell execution."""

from __future__ import annotations

from pathlib import Path
from typing import Any

from app.tools.base import Tool
from app.tools.create_note import CreateNoteTool
from app.tools.delete_demo_file import DeleteDemoFileTool
from app.tools.execute_demo_task import ExecuteDemoTaskTool
from app.tools.list_files import ListFilesTool
from app.tools.modify_configuration import ModifyConfigurationTool
from app.tools.read_file import ReadFileTool
from app.tools.send_notification import SendNotificationTool


class UnknownToolError(Exception):
    pass


class ToolRegistry:
    def __init__(self, workspace: Path) -> None:
        self.workspace = workspace
        workspace.mkdir(parents=True, exist_ok=True)
        (workspace / "notes").mkdir(exist_ok=True)
        notes = workspace / "project-notes.txt"
        if not notes.exists():
            notes.write_text(
                "AgentGuard demo notes\n"
                "=====================\n"
                "This sandbox is used for safe tool demonstrations.\n"
                "Tools may only read/write inside this workspace.\n",
                encoding="utf-8",
            )
        report = workspace / "old-report.pdf"
        if not report.exists():
            report.write_text("DEMO REPORT — safe to delete in sandbox.\n", encoding="utf-8")

        self._tools: dict[str, Tool] = {
            t.metadata.name: t
            for t in [
                ReadFileTool(workspace),
                ListFilesTool(workspace),
                CreateNoteTool(workspace),
                DeleteDemoFileTool(workspace),
                SendNotificationTool(),
                ModifyConfigurationTool(workspace),
                ExecuteDemoTaskTool(),
            ]
        }

    def get(self, name: str) -> Tool:
        tool = self._tools.get(name)
        if tool is None:
            raise UnknownToolError(f"Unknown tool: {name}")
        return tool

    def list_tools(self) -> list[Tool]:
        return list(self._tools.values())

    def execute(self, name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        return self.get(name).execute(arguments)
