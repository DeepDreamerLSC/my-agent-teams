from __future__ import annotations

import json
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Mapping

SESSION_STATUSES = {
    "unknown",
    "online",
    "idle",
    "busy",
    "waiting_approval",
    "blocked",
    "offline",
    "ended",
    "error",
    "unsupported",
}

EVENT_TYPES = {
    "registered",
    "heartbeat",
    "status",
    "gate_changed",
    "artifact_attached",
    "error",
    "ended",
    "unbound",
}


def now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds")


def new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex}"


def json_dumps(value: Any) -> str:
    return json.dumps(value if value is not None else {}, ensure_ascii=False, sort_keys=True)


def json_loads(value: Any, default: Any) -> Any:
    if value in (None, ""):
        return default
    try:
        return json.loads(value)
    except (TypeError, ValueError):
        return default


def row_to_dict(row: Mapping[str, Any] | None) -> dict[str, Any] | None:
    if row is None:
        return None
    item = dict(row)
    list_keys = {"acceptance_json", "options_json"}
    for key in (
        "capabilities_json",
        "metadata_json",
        "acceptance_json",
        "payload_json",
        "output_json",
        "options_json",
        "decision_json",
        "manifest_json",
        "previous_json",
        "next_json",
    ):
        if key in item:
            item[key.removesuffix("_json")] = json_loads(item[key], [] if key in list_keys else {})
            del item[key]
    return item


def resolve_path(value: str | Path) -> Path:
    return Path(value).expanduser().resolve()


def is_relative_to(path: Path, root: Path) -> bool:
    try:
        path.relative_to(root)
        return True
    except ValueError:
        return False
