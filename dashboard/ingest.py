from __future__ import annotations

import hashlib
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any

from .db import connect_db, resolve_db_path, upsert_event, upsert_task, utcnow_iso

PENDING_BOARD_STATUSES = {'pending', 'dispatched'}
BLOCKED_STATUSES = {'blocked', 'failed', 'cancelled', 'timeout'}
DONE_STATUSES = {'merged', 'archived'}
APPROVE_KEYWORDS = ('通过', 'approve', 'approved')
REJECT_KEYWORDS = ('驳回', '不通过', '未通过', 'reject', 'blocked', 'request changes', '不接受')
REVIEW_HINT_KEYWORDS = ('review', '审查', '验收')


def map_board_status(current_status: str | None) -> str:
    normalized = (current_status or 'pending').strip() or 'pending'
    if normalized in PENDING_BOARD_STATUSES:
        return 'pending'
    if normalized == 'working':
        return 'working'
    if normalized == 'ready_for_merge':
        return 'ready_for_merge'
    if normalized in BLOCKED_STATUSES:
        return 'blocked'
    if normalized in DONE_STATUSES:
        return 'done'
    return normalized


def discover_task_dirs(tasks_root: str | Path) -> list[Path]:
    root = Path(tasks_root).expanduser().resolve()
    if not root.exists():
        return []
    return sorted(
        task_dir for task_dir in root.iterdir()
        if task_dir.is_dir() and (task_dir / 'task.json').exists()
    )


def _load_json(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except json.JSONDecodeError:
        return None


def _load_transitions(path: Path) -> list[dict[str, Any]]:
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    for index, raw_line in enumerate(path.read_text(encoding='utf-8').splitlines(), start=1):
        line = raw_line.strip()
        if not line:
            continue
        try:
            payload = json.loads(line)
        except json.JSONDecodeError:
            payload = {'raw': line}
        payload['_line_number'] = index
        rows.append(payload)
    return rows


def _coalesce(*values: Any) -> Any:
    for value in values:
        if value is None:
            continue
        if isinstance(value, str) and not value.strip():
            continue
        return value
    return None


def _get_first(mapping: dict[str, Any] | None, *keys: str) -> Any:
    if not mapping:
        return None
    for key in keys:
        if key in mapping:
            value = mapping.get(key)
            if isinstance(value, str):
                value = value.strip()
            if value not in (None, ''):
                return value
    return None


def _normalize_time(value: Any) -> str | None:
    if value is None:
        return None
    if isinstance(value, (int, float)):
        return datetime.fromtimestamp(float(value)).astimezone().isoformat(timespec='seconds')
    if not isinstance(value, str):
        return None
    candidate = value.strip()
    if not candidate:
        return None
    try:
        return datetime.fromisoformat(candidate.replace('Z', '+00:00')).astimezone().isoformat(timespec='seconds')
    except ValueError:
        return None


def _file_mtime(path: Path) -> str | None:
    if not path.exists():
        return None
    return datetime.fromtimestamp(path.stat().st_mtime).astimezone().isoformat(timespec='seconds')


def _json_dumps(value: Any) -> str:
    return json.dumps(value, ensure_ascii=False, sort_keys=True)


def _make_transition_event_key(task_id: str, transition: dict[str, Any]) -> str:
    raw = _json_dumps({
        'line_number': transition.get('_line_number'),
        'from': transition.get('from'),
        'to': transition.get('to'),
        'at': transition.get('at'),
        'reason': transition.get('reason'),
        'raw': transition.get('raw'),
    })
    digest = hashlib.sha1(raw.encode('utf-8')).hexdigest()[:12]
    return f'{task_id}:transition:{transition.get("_line_number", 0)}:{digest}'


def _review_state(review_text: str | None) -> str | None:
    if not review_text:
        return None
    lowered = review_text.lower()
    has_reject = any(keyword in lowered for keyword in REJECT_KEYWORDS) or any(keyword in review_text for keyword in REJECT_KEYWORDS)
    has_approve = any(keyword in lowered for keyword in APPROVE_KEYWORDS) or any(keyword in review_text for keyword in APPROVE_KEYWORDS)
    if has_reject:
        return 'changes_requested'
    if has_approve:
        return 'approved'
    return 'present'


def _bool_value(mapping: dict[str, Any] | None, *keys: str) -> int | None:
    if not mapping:
        return None
    for key in keys:
        if key not in mapping:
            continue
        value = mapping.get(key)
        if isinstance(value, bool):
            return int(value)
        if isinstance(value, str):
            lowered = value.strip().lower()
            if lowered in {'true', '1', 'yes', 'ok', 'pass'}:
                return 1
            if lowered in {'false', '0', 'no', 'fail'}:
                return 0
        if isinstance(value, (int, float)):
            return int(bool(value))
    return None


def _first_transition_at(transitions: list[dict[str, Any]], *, to_status: str) -> str | None:
    for transition in transitions:
        if transition.get('to') == to_status:
            normalized = _normalize_time(transition.get('at'))
            if normalized:
                return normalized
    return None


def _last_transition_at(transitions: list[dict[str, Any]], *, to_status: str) -> str | None:
    for transition in reversed(transitions):
        if transition.get('to') == to_status:
            normalized = _normalize_time(transition.get('at'))
            if normalized:
                return normalized
    return None


def _latest_review_transition_at(transitions: list[dict[str, Any]]) -> str | None:
    for transition in reversed(transitions):
        reason = str(transition.get('reason') or '')
        lowered = reason.lower()
        if any(keyword in lowered for keyword in REVIEW_HINT_KEYWORDS) or any(keyword in reason for keyword in REVIEW_HINT_KEYWORDS):
            normalized = _normalize_time(transition.get('at'))
            if normalized:
                return normalized
    return None


def _build_events(
    *,
    task_id: str,
    task_dir: Path,
    task: dict[str, Any],
    transitions: list[dict[str, Any]],
    ack: dict[str, Any] | None,
    result: dict[str, Any] | None,
    review_text: str | None,
    verify: dict[str, Any] | None,
) -> list[dict[str, Any]]:
    observed_at = utcnow_iso()
    events: list[dict[str, Any]] = []
    task_json_path = task_dir / 'task.json'
    created_at = _coalesce(_normalize_time(task.get('created_at')), _file_mtime(task_json_path))
    if created_at:
        events.append({
            'event_key': f'{task_id}:created',
            'task_id': task_id,
            'event_type': 'created',
            'event_at': created_at,
            'source': 'task_json',
            'status_from': None,
            'status_to': task.get('status'),
            'artifact_path': str(task_json_path),
            'payload_json': _json_dumps({'created_at': created_at, 'status': task.get('status')}),
            'observed_at': observed_at,
        })

    for transition in transitions:
        events.append({
            'event_key': _make_transition_event_key(task_id, transition),
            'task_id': task_id,
            'event_type': 'status_transition',
            'event_at': _normalize_time(transition.get('at')),
            'source': 'transitions_jsonl',
            'status_from': transition.get('from'),
            'status_to': transition.get('to'),
            'artifact_path': str(task_dir / 'transitions.jsonl'),
            'payload_json': _json_dumps({
                'reason': transition.get('reason'),
                'line_number': transition.get('_line_number'),
                'raw': transition.get('raw'),
            }),
            'observed_at': observed_at,
        })

    if ack is not None:
        events.append({
            'event_key': f'{task_id}:ack',
            'task_id': task_id,
            'event_type': 'ack',
            'event_at': _coalesce(
                _normalize_time(_get_first(ack, 'acknowledged_at', 'acked_at', 'timestamp')),
                _file_mtime(task_dir / 'ack.json'),
            ),
            'source': 'ack_json',
            'status_from': None,
            'status_to': 'working',
            'artifact_path': str(task_dir / 'ack.json'),
            'payload_json': _json_dumps({
                'agent': _coalesce(_get_first(ack, 'agent_id', 'agent'), task.get('assigned_agent')),
                'status': ack.get('status'),
            }),
            'observed_at': observed_at,
        })

    if result is not None:
        events.append({
            'event_key': f'{task_id}:result',
            'task_id': task_id,
            'event_type': 'result',
            'event_at': _coalesce(
                _normalize_time(_get_first(result, 'completed_at', 'reported_at')),
                _file_mtime(task_dir / 'result.json'),
            ),
            'source': 'result_json',
            'status_from': None,
            'status_to': task.get('status'),
            'artifact_path': str(task_dir / 'result.json'),
            'payload_json': _json_dumps({
                'agent': _coalesce(_get_first(result, 'agent_id', 'agent'), task.get('assigned_agent')),
                'status': result.get('status'),
                'summary': result.get('summary'),
            }),
            'observed_at': observed_at,
        })

    if review_text is not None:
        events.append({
            'event_key': f'{task_id}:review',
            'task_id': task_id,
            'event_type': 'review_completed',
            'event_at': _file_mtime(task_dir / 'review.md'),
            'source': 'review_md',
            'status_from': None,
            'status_to': task.get('status'),
            'artifact_path': str(task_dir / 'review.md'),
            'payload_json': _json_dumps({'review_state': _review_state(review_text)}),
            'observed_at': observed_at,
        })

    if verify is not None:
        events.append({
            'event_key': f'{task_id}:verify',
            'task_id': task_id,
            'event_type': 'verify_completed',
            'event_at': _coalesce(
                _normalize_time(_get_first(verify, 'verified_at', 'completed_at', 'reported_at')),
                _file_mtime(task_dir / 'verify.json'),
            ),
            'source': 'verify_json',
            'status_from': None,
            'status_to': task.get('status'),
            'artifact_path': str(task_dir / 'verify.json'),
            'payload_json': _json_dumps({'ok': _bool_value(verify, 'ok', 'pass')}),
            'observed_at': observed_at,
        })

    return events


def _build_task_record(
    *,
    task_dir: Path,
    task: dict[str, Any],
    transitions: list[dict[str, Any]],
    ack: dict[str, Any] | None,
    result: dict[str, Any] | None,
    review_text: str | None,
    verify: dict[str, Any] | None,
    source: str,
) -> dict[str, Any]:
    task_id = str(task.get('id') or task_dir.name)
    created_at = _coalesce(
        _normalize_time(task.get('created_at')),
        _file_mtime(task_dir / 'task.json'),
    )
    dispatched_at = _coalesce(
        _first_transition_at(transitions, to_status='dispatched'),
        _normalize_time(task.get('lease_acquired_at')) if task.get('status') in {'dispatched', 'working', 'ready_for_merge', 'blocked', 'merged', 'archived'} else None,
    )
    ack_at = _coalesce(
        _normalize_time(_get_first(ack, 'acknowledged_at', 'acked_at', 'timestamp')),
        _first_transition_at(transitions, to_status='working'),
    )
    completed_at = _coalesce(
        _normalize_time(_get_first(result, 'completed_at', 'reported_at')),
        _file_mtime(task_dir / 'result.json') if result is not None else None,
        _first_transition_at(transitions, to_status='ready_for_merge'),
    )
    review_completed_at = _coalesce(
        _latest_review_transition_at(transitions),
        _file_mtime(task_dir / 'review.md') if review_text is not None else None,
    )
    verify_completed_at = _coalesce(
        _normalize_time(_get_first(verify, 'verified_at', 'completed_at', 'reported_at')),
        _file_mtime(task_dir / 'verify.json') if verify is not None else None,
    )
    current_status = str(task.get('status') or 'pending')
    current_status_at = _coalesce(
        _last_transition_at(transitions, to_status=current_status),
        _normalize_time(task.get('updated_at')),
        verify_completed_at,
        review_completed_at,
        completed_at,
        ack_at,
        dispatched_at,
        created_at,
    )
    return {
        'task_id': task_id,
        'title': str(task.get('title') or task_id),
        'project': task.get('project'),
        'domain': task.get('domain'),
        'assigned_agent': task.get('assigned_agent'),
        'reviewer': task.get('reviewer'),
        'owner_pm': task.get('owner_pm'),
        'parent_task_id': task.get('parent_task_id'),
        'root_request_id': task.get('root_request_id'),
        'review_required': int(bool(task.get('review_required'))),
        'test_required': int(bool(task.get('test_required'))),
        'current_status': current_status,
        'board_status': map_board_status(current_status),
        'created_at': created_at,
        'dispatched_at': dispatched_at,
        'ack_at': ack_at,
        'completed_at': completed_at,
        'review_completed_at': review_completed_at,
        'verify_completed_at': verify_completed_at,
        'current_status_at': current_status_at,
        'ack_agent': _coalesce(_get_first(ack, 'agent_id', 'agent'), task.get('assigned_agent')),
        'result_agent': _coalesce(_get_first(result, 'agent_id', 'agent'), _get_first(ack, 'agent_id', 'agent'), task.get('assigned_agent')),
        'lease_acquired_at': _normalize_time(task.get('lease_acquired_at')),
        'updated_at': _normalize_time(task.get('updated_at')),
        'summary': _coalesce(_get_first(result, 'summary'), task.get('result_summary')),
        'review_state': _review_state(review_text),
        'verify_ok': _bool_value(verify, 'ok', 'pass'),
        'task_dir': str(task_dir),
        'task_json_path': str(task_dir / 'task.json'),
        'write_scope_json': _json_dumps(task.get('write_scope') or []),
        'artifacts_json': _json_dumps(task.get('artifacts') or []),
        'last_ingest_source': source,
        'last_synced_at': utcnow_iso(),
    }


def sync_task_dir(
    task_dir: str | Path,
    *,
    db_path: str | Path | None = None,
    source: str = 'manual',
    conn: sqlite3.Connection | None = None,
) -> dict[str, Any]:
    task_dir_path = Path(task_dir).expanduser().resolve()
    task = _load_json(task_dir_path / 'task.json')
    if task is None:
        raise FileNotFoundError(f'missing or invalid task.json: {task_dir_path / "task.json"}')

    transitions = _load_transitions(task_dir_path / 'transitions.jsonl')
    ack = _load_json(task_dir_path / 'ack.json')
    result = _load_json(task_dir_path / 'result.json')
    verify = _load_json(task_dir_path / 'verify.json')
    review_path = task_dir_path / 'review.md'
    review_text = review_path.read_text(encoding='utf-8') if review_path.exists() else None
    task_id = str(task.get('id') or task_dir_path.name)

    task_record = _build_task_record(
        task_dir=task_dir_path,
        task=task,
        transitions=transitions,
        ack=ack,
        result=result,
        review_text=review_text,
        verify=verify,
        source=source,
    )
    events = _build_events(
        task_id=task_id,
        task_dir=task_dir_path,
        task=task,
        transitions=transitions,
        ack=ack,
        result=result,
        review_text=review_text,
        verify=verify,
    )

    own_connection = conn is None
    if own_connection:
        conn = connect_db(db_path)

    assert conn is not None
    with conn:
        upsert_task(conn, task_record)
        for event in events:
            upsert_event(conn, event)

    if own_connection:
        conn.close()

    return {
        'task_id': task_id,
        'db_path': str(resolve_db_path(db_path)),
        'event_count': len(events),
        'current_status': task_record['current_status'],
        'board_status': task_record['board_status'],
    }


def backfill_tasks(
    tasks_root: str | Path,
    *,
    db_path: str | Path | None = None,
    source: str = 'backfill',
) -> dict[str, Any]:
    task_dirs = discover_task_dirs(tasks_root)
    conn = connect_db(db_path)
    summaries: list[dict[str, Any]] = []
    try:
        for task_dir in task_dirs:
            summaries.append(sync_task_dir(task_dir, db_path=db_path, source=source, conn=conn))
    finally:
        conn.close()
    return {
        'tasks_root': str(Path(tasks_root).expanduser().resolve()),
        'db_path': str(resolve_db_path(db_path)),
        'task_count': len(task_dirs),
        'synced_tasks': summaries,
    }
