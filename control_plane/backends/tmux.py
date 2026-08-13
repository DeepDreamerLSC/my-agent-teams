from __future__ import annotations

import subprocess
from typing import Any, Callable, Mapping, Sequence

from .base import BackendHealth


class TmuxBackend:
    """Compatibility backend for existing configured tmux sessions."""

    name = "tmux"

    def __init__(
        self,
        *,
        runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
        command: str = "tmux",
    ) -> None:
        self.runner = runner or subprocess.run
        self.command = command

    def capabilities(self) -> Mapping[str, Any]:
        return {
            "health_probe": True,
            "heartbeat": False,
            "thread_metadata": False,
            "artifact_events": False,
            "status": "supported",
        }

    def register(self, session: Mapping[str, Any]) -> Mapping[str, Any]:
        return {"backend": self.name, "registered": True, "capabilities": dict(self.capabilities())}

    def create(self, request: Mapping[str, Any]) -> Mapping[str, Any]:
        return {"created": False, "status": "unsupported", "reason": "tmux creation remains a compatibility path; use teamctl"}

    def disconnect(self, session: Mapping[str, Any]) -> Mapping[str, Any]:
        return {"backend": self.name, "disconnected": True}

    def health(self, session: Mapping[str, Any]) -> BackendHealth:
        tmux_session = str(session.get("tmux_session") or session.get("external_ref") or "").strip()
        if not tmux_session:
            return BackendHealth("unknown", "tmux session name is missing", self.capabilities())
        try:
            result = self.runner(
                [self.command, "has-session", "-t", tmux_session],
                capture_output=True,
                text=True,
                check=False,
            )
        except (OSError, PermissionError) as exc:
            return BackendHealth("unknown", f"tmux probe unavailable: {exc}", self.capabilities())
        if result.returncode == 0:
            return BackendHealth("online", None, self.capabilities())
        stderr = (result.stderr or "").strip()
        if "permission" in stderr.lower() or "socket" in stderr.lower():
            return BackendHealth("unknown", stderr or "tmux socket is unavailable", self.capabilities())
        return BackendHealth("offline", stderr or "tmux session not found", self.capabilities())
