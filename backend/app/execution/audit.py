"""Structured audit trail helpers."""

from __future__ import annotations

from typing import Any

from app.guard.models import AuditEvent


def event(
    stage: str, name: str, *, duration_ms: float | None = None, **metadata: Any
) -> AuditEvent:
    # Strip anything that looks like a secret key name
    safe = {
        k: v for k, v in metadata.items() if "key" not in k.lower() and "secret" not in k.lower()
    }
    return AuditEvent(stage=stage, event=name, metadata=safe, duration_ms=duration_ms)
