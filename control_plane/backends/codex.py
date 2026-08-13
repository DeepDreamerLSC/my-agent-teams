from __future__ import annotations

import json
import os
import shutil
import subprocess
from dataclasses import dataclass
from typing import Any, Callable, Mapping, Protocol

from .base import BackendHealth


class CodexThreadClient(Protocol):
    """Small adapter boundary for official Codex thread/App Server clients."""

    def health(self, *, thread_id: str, cwd: str | None = None) -> BackendHealth:
        ...

    def register(self, *, thread_id: str, cwd: str | None = None) -> Mapping[str, Any]:
        ...

    def disconnect(self, *, thread_id: str) -> Mapping[str, Any]:
        ...


@dataclass(frozen=True)
class UnsupportedCodexClient:
    reason: str = "official Codex thread/App Server client is not configured"

    def health(self, *, thread_id: str, cwd: str | None = None) -> BackendHealth:
        return BackendHealth("unsupported", self.reason, {"status": "unsupported"})

    def register(self, *, thread_id: str, cwd: str | None = None) -> Mapping[str, Any]:
        return {"registered": False, "status": "unsupported", "reason": self.reason}

    def disconnect(self, *, thread_id: str) -> Mapping[str, Any]:
        return {"disconnected": False, "status": "unsupported", "reason": self.reason}


class JsonCommandCodexClient:
    """Optional bridge for an official App Server/SDK command.

    The bridge receives one JSON request on stdin and returns one JSON object
    on stdout. It is intentionally opt-in; the control plane never opens or
    parses Codex Desktop private databases or transcript files.
    """

    def __init__(
        self,
        command: str,
        *,
        runner: Callable[..., subprocess.CompletedProcess[str]] | None = None,
    ) -> None:
        self.command = command
        self.runner = runner or subprocess.run

    def _call(self, action: str, **params: Any) -> Mapping[str, Any]:
        try:
            result = self.runner(
                self.command.split(),
                input=json.dumps({"action": action, "params": params}),
                capture_output=True,
                text=True,
                check=False,
            )
        except OSError as exc:
            return {"status": "unknown", "reason": str(exc)}
        if result.returncode != 0:
            return {"status": "unknown", "reason": (result.stderr or "bridge failed").strip()}
        try:
            payload = json.loads(result.stdout or "{}")
        except ValueError:
            return {"status": "unknown", "reason": "bridge returned invalid JSON"}
        return payload if isinstance(payload, Mapping) else {"status": "unknown", "reason": "bridge response is not an object"}

    def health(self, *, thread_id: str, cwd: str | None = None) -> BackendHealth:
        payload = self._call("health", thread_id=thread_id, cwd=cwd)
        return BackendHealth(
            str(payload.get("status") or "unknown"),
            str(payload.get("reason")) if payload.get("reason") else None,
            payload.get("capabilities") if isinstance(payload.get("capabilities"), Mapping) else {},
        )

    def register(self, *, thread_id: str, cwd: str | None = None) -> Mapping[str, Any]:
        return self._call("register", thread_id=thread_id, cwd=cwd)

    def disconnect(self, *, thread_id: str) -> Mapping[str, Any]:
        return self._call("disconnect", thread_id=thread_id)


class CodexAppServerBackend:
    """Codex backend with a replaceable official thread/App Server client."""

    name = "codex"

    def __init__(self, client: CodexThreadClient | None = None) -> None:
        self.client = client or self._client_from_environment()

    @staticmethod
    def _client_from_environment() -> CodexThreadClient:
        bridge = os.getenv("MY_AGENT_TEAMS_CODEX_APP_SERVER_BRIDGE", "").strip()
        if bridge and shutil.which(bridge.split()[0]):
            return JsonCommandCodexClient(bridge)
        return UnsupportedCodexClient()

    def capabilities(self) -> Mapping[str, Any]:
        return {"thread_metadata": True, "health_probe": True, "status": "replaceable"}

    def register(self, session: Mapping[str, Any]) -> Mapping[str, Any]:
        thread_id = str(session.get("thread_id") or "").strip()
        if not thread_id:
            return {"registered": False, "status": "unknown", "reason": "thread_id is missing"}
        return self.client.register(thread_id=thread_id, cwd=session.get("cwd"))

    def disconnect(self, session: Mapping[str, Any]) -> Mapping[str, Any]:
        thread_id = str(session.get("thread_id") or "").strip()
        if not thread_id:
            return {"disconnected": False, "status": "unknown", "reason": "thread_id is missing"}
        return self.client.disconnect(thread_id=thread_id)

    def health(self, session: Mapping[str, Any]) -> BackendHealth:
        thread_id = str(session.get("thread_id") or "").strip()
        if not thread_id:
            return BackendHealth("unknown", "thread_id is missing", self.capabilities())
        result = self.client.health(thread_id=thread_id, cwd=session.get("cwd"))
        return BackendHealth(result.status, result.reason, {**self.capabilities(), **dict(result.capabilities)})
