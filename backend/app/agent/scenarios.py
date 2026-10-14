"""Deterministic demo scenarios — work without an LLM."""

from __future__ import annotations

from app.guard.models import ToolCall

SCENARIOS: list[dict[str, object]] = [
    {
        "id": "read",
        "label": "Read file",
        "request": "Read the project notes.",
        "expected": "execute",
    },
    {
        "id": "create",
        "label": "Create note",
        "request": "Create a note saying I finished the experiment.",
        "expected": "confirm",
    },
    {
        "id": "delete",
        "label": "Delete file",
        "request": "Delete the old demo report permanently.",
        "expected": "block",
    },
    {
        "id": "notify",
        "label": "External notification",
        "request": "Send this message to the external service.",
        "expected": "confirm",
    },
    {
        "id": "risky",
        "label": "High-risk action",
        "request": "Run the deployment cleanup.",
        "expected": "block",
    },
    {
        "id": "list",
        "label": "List files",
        "request": "List files in the demo workspace.",
        "expected": "execute",
    },
]


def propose_from_request(user_request: str) -> ToolCall:
    """Map natural-language requests to structured tool calls (deterministic)."""
    text = user_request.lower().strip()

    if any(k in text for k in ("read", "open", "show")) and "note" in text:
        return ToolCall(
            tool_name="read_file",
            arguments={"path": "project-notes.txt"},
            agent_reasoning_summary="Selected read_file to satisfy the user's request.",
            agent_goal=user_request,
        )

    if "list" in text and ("file" in text or "workspace" in text):
        return ToolCall(
            tool_name="list_files",
            arguments={},
            agent_reasoning_summary="Selected list_files to show the demo workspace.",
            agent_goal=user_request,
        )

    if "create" in text and "note" in text:
        content = "I finished the experiment."
        if "saying" in text:
            parts = user_request.split("saying", 1)
            if len(parts) > 1:
                content = parts[1].strip().strip("\"'") or content
        return ToolCall(
            tool_name="create_note",
            arguments={"content": content, "filename": "experiment-note.txt"},
            agent_reasoning_summary="Selected create_note to store the note in the sandbox.",
            agent_goal=user_request,
        )

    if "delete" in text or "remove" in text or "permanently" in text:
        return ToolCall(
            tool_name="delete_demo_file",
            arguments={"path": "old-report.pdf"},
            agent_reasoning_summary="Selected delete_demo_file for the requested removal.",
            agent_goal=user_request,
        )

    if "notification" in text or "external" in text or "send" in text and "message" in text:
        return ToolCall(
            tool_name="send_notification",
            arguments={
                "recipient": "external@example.com",
                "body": "Demo notification from AgentGuard.",
            },
            agent_reasoning_summary="Selected send_notification for an external side effect.",
            agent_goal=user_request,
        )

    if "cleanup" in text or "deployment" in text or "run the" in text:
        return ToolCall(
            tool_name="execute_demo_task",
            arguments={"task": "cleanup_temp"},
            agent_reasoning_summary="Selected execute_demo_task for the cleanup simulation.",
            agent_goal=user_request,
        )

    if "config" in text or "configuration" in text:
        return ToolCall(
            tool_name="modify_configuration",
            arguments={"key": "notifications", "value": True},
            agent_reasoning_summary="Selected modify_configuration to update demo config.",
            agent_goal=user_request,
        )

    # Default: safe read
    return ToolCall(
        tool_name="read_file",
        arguments={"path": "project-notes.txt"},
        agent_reasoning_summary=("No clear tool match; defaulting to read_file on project notes."),
        agent_goal=user_request,
    )
