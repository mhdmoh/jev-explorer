"""Tool protocol and metadata."""

from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Any

from app.guard.models import ToolMetadata


class Tool(ABC):
    """Sandboxed demo tool."""

    @property
    @abstractmethod
    def metadata(self) -> ToolMetadata: ...

    @abstractmethod
    def execute(self, arguments: dict[str, Any]) -> dict[str, Any]:
        """Run the tool and return a JSON-serializable result."""
