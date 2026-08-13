from __future__ import annotations

from typing import Any, Mapping

from .base import BackendHealth


class FakeBackend:
    """Deterministic backend used by contract and integration tests."""

    name = "fake"

    def __init__(self, *, status: str = "online") -> None:
        self.status = status
        self.registered: list[str] = []
        self.disconnected: list[str] = []

    def capabilities(self) -> Mapping[str, Any]:
        return {"health_probe": True, "heartbeat": True, "status": "test"}

    def health(self, session: Mapping[str, Any]) -> BackendHealth:
        return BackendHealth(self.status, None if self.status == "online" else self.status, self.capabilities())

    def register(self, session: Mapping[str, Any]) -> Mapping[str, Any]:
        self.registered.append(str(session.get("session_id")))
        return {"registered": True, "status": self.status}

    def disconnect(self, session: Mapping[str, Any]) -> Mapping[str, Any]:
        self.disconnected.append(str(session.get("session_id")))
        return {"disconnected": True}
