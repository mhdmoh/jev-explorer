"""Path confinement helpers for demo tools."""

from __future__ import annotations

from pathlib import Path


class SandboxError(Exception):
    pass


def resolve_in_workspace(workspace: Path, relative: str) -> Path:
    """Resolve a path that must stay inside the demo workspace."""
    workspace = workspace.resolve()
    candidate = (workspace / relative).resolve()
    try:
        candidate.relative_to(workspace)
    except ValueError as exc:
        raise SandboxError(f"Path escapes demo workspace: {relative}") from exc
    return candidate
