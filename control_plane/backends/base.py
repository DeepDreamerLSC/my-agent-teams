from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any, Mapping, Protocol


@dataclass(frozen=True)
class BackendHealth:
    status: str
    reason: str | None = None
    capabilities: Mapping[str, Any] = field(default_factory=dict)


class ExecutionBackend(Protocol):
    """Backend contract used by the control plane.

    Backends report facts. They do not own workflow gates or write project
    files. A backend that cannot inspect a session must return unsupported or
    unknown rather than claiming that the session is online.
    """

    name: str

    def health(self, session: Mapping[str, Any]) -> BackendHealth:
        ...

    def capabilities(self) -> Mapping[str, Any]:
        ...

    def register(self, session: Mapping[str, Any]) -> Mapping[str, Any]:
        ...

    def create(self, request: Mapping[str, Any]) -> Mapping[str, Any]:
        ...

    def disconnect(self, session: Mapping[str, Any]) -> Mapping[str, Any]:
        ...
