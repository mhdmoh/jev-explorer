from __future__ import annotations

from typing import Any

from app.guard.models import ActionType, ToolMetadata
from app.tools.base import Tool


class SendNotificationTool(Tool):
    """Simulated external side effect — never sends a real message."""

    @property
    def metadata(self) -> ToolMetadata:
        return ToolMetadata(
            name="send_notification",
            description="Simulate sending an external notification (no real I/O).",
            category=ActionType.EXTERNAL_SIDE_EFFECT,
            reversible=False,
            external_side_effect=True,
            destructive=False,
            requires_confirmation=True,
        )

    def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        recipient = str(arguments.get("recipient") or "external@example.com")
        body = str(arguments.get("body") or "")
        return {
            "ok": True,
            "simulated": True,
            "recipient": recipient,
            "body_preview": body[:120],
            "message": "Notification simulated — no external message was sent.",
        }
