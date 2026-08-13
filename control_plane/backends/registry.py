from __future__ import annotations

from typing import Mapping

from .base import ExecutionBackend
from .codex import CodexAppServerBackend
from .tmux import TmuxBackend


class BackendRegistry:
    def __init__(self, backends: Mapping[str, ExecutionBackend] | None = None) -> None:
        self.backends = dict(backends or {"tmux": TmuxBackend(), "codex": CodexAppServerBackend()})

    def get(self, name: str) -> ExecutionBackend:
        try:
            return self.backends[name]
        except KeyError as exc:
            raise KeyError(f"unsupported execution backend: {name}") from exc
