"""Sandbox tool tests."""

from __future__ import annotations

from pathlib import Path

import pytest
from app.tools._sandbox import SandboxError, resolve_in_workspace
from app.tools.registry import ToolRegistry, UnknownToolError


def test_workspace_confinement(tmp_path: Path) -> None:
    with pytest.raises(SandboxError):
        resolve_in_workspace(tmp_path, "../outside.txt")


def test_read_and_list(tmp_path: Path) -> None:
    registry = ToolRegistry(tmp_path)
    listed = registry.execute("list_files", {})
    assert listed["ok"] is True
    assert "project-notes.txt" in listed["files"]

    read = registry.execute("read_file", {"path": "project-notes.txt"})
    assert read["ok"] is True
    assert "AgentGuard" in read["content"]


def test_delete_only_inside_workspace(tmp_path: Path) -> None:
    registry = ToolRegistry(tmp_path)
    result = registry.execute("delete_demo_file", {"path": "old-report.pdf"})
    assert result["ok"] is True
    assert not (tmp_path / "old-report.pdf").exists()

    escaped = registry.execute("delete_demo_file", {"path": "../../etc/passwd"})
    assert escaped["ok"] is False


def test_unknown_tool(tmp_path: Path) -> None:
    registry = ToolRegistry(tmp_path)
    with pytest.raises(UnknownToolError):
        registry.get("rm_rf")


def test_execute_demo_task_rejects_arbitrary(tmp_path: Path) -> None:
    registry = ToolRegistry(tmp_path)
    result = registry.execute("execute_demo_task", {"task": "rm -rf /"})
    assert result["ok"] is False
