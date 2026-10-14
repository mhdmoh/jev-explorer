"""Tool executor — runs only after policy (and optional human) approval."""

from __future__ import annotations

from typing import Any

from app.guard.models import ExecutionResult, ToolCall
from app.tools.registry import ToolRegistry, UnknownToolError
from app.utils.timing import Timer


class ToolExecutor:
    def __init__(self, registry: ToolRegistry) -> None:
        self._registry = registry

    def run(self, tool_call: ToolCall) -> ExecutionResult:
        with Timer() as timer:
            try:
                output = self._registry.execute(tool_call.tool_name, tool_call.arguments)
            except UnknownToolError as exc:
                return ExecutionResult(
                    executed=False,
                    success=False,
                    message=str(exc),
                    latency_ms=timer.elapsed_ms,
                )
            except Exception as exc:  # noqa: BLE001 — surface tool failures cleanly
                return ExecutionResult(
                    executed=True,
                    success=False,
                    message=f"Tool failed: {exc}",
                    latency_ms=timer.elapsed_ms,
                )

        ok = bool(output.get("ok", True)) if isinstance(output, dict) else True
        message = _message_from_output(output, ok)
        return ExecutionResult(
            executed=True,
            success=ok,
            message=message,
            output=output,
            latency_ms=timer.elapsed_ms,
        )


def _message_from_output(output: Any, ok: bool) -> str:
    if isinstance(output, dict):
        if not ok:
            return str(output.get("error") or "Tool reported failure")
        if "message" in output:
            return str(output["message"])
        if "content" in output:
            return "File read successfully."
        if "deleted" in output:
            return f"Demo file deleted: {output['deleted']}"
        if "path" in output and "bytes" in output:
            return f"Note created at {output['path']}"
        if "files" in output:
            return f"Listed {len(output['files'])} file(s)."
        if "result" in output:
            return str(output["result"])
        return "Tool completed."
    return "Tool completed."
