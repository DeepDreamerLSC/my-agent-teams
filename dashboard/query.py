from __future__ import annotations

import json
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ACTIVE_LOAD_STATUSES = {'pending', 'dispatched', 'working', 'blocked'}
BLOCKED_AGGREGATE_STATUSES = {'blocked', 'failed', 'cancelled', 'timeout'}
READ_ONLY_AGGREGATE_DIMENSIONS = (
    'owner_pm',
    'domain',
    'task_level',
    'parent_task_id',
    'root_request_id',
)


def _parse_time(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00'))
    except ValueError:
        return None


def _seconds_between(start: str | None, end: str | None) -> float | None:
    start_dt = _parse_time(start)
    end_dt = _parse_time(end)
    if start_dt is None or end_dt is None:
        return None
    return max((end_dt - start_dt).total_seconds(), 0.0)


def _now_iso() -> str:
    return datetime.now(timezone.utc).astimezone().isoformat(timespec='seconds')


def _duration_hours(seconds: float | None) -> float | None:
    if seconds is None:
        return None
    return round(seconds / 3600, 3)


def _persisted_stage_durations_from_row(row: sqlite3.Row) -> dict[str, float | None]:
    keys = (
        'create_to_dispatch_seconds',
        'dispatch_to_ack_seconds',
        'ack_to_result_seconds',
        'result_to_review_seconds',
        'review_to_verify_seconds',
        'verify_to_close_seconds',
        'total_cycle_seconds',
    )
    row_keys = set(row.keys())
    return {key: row[key] if key in row_keys else None for key in keys}


def _row_to_task(row: sqlite3.Row) -> dict[str, Any]:
    write_scope = json.loads(row['write_scope_json'] or '[]')
    artifacts = json.loads(row['artifacts_json'] or '[]')
    started_at = row['ack_at'] or row['dispatched_at'] or row['created_at']
    active_until = row['completed_at'] or row['current_status_at'] or _now_iso()
    active_work_seconds = _seconds_between(started_at, active_until)
    return {
        'task_id': row['task_id'],
        'title': row['title'],
        'project': row['project'],
        'domain': row['domain'],
        'assigned_agent': row['assigned_agent'],
        'reviewer': row['reviewer'],
        'owner_pm': row['owner_pm'],
        'integration_owner': row['integration_owner'],
        'parent_task_id': row['parent_task_id'],
        'root_request_id': row['root_request_id'],
        'target_environment': row['target_environment'],
        'priority': row['priority'],
        'review_level': row['review_level'],
        'current_status': row['current_status'],
        'board_status': row['board_status'],
        'merge_gate_state': row['merge_gate_state'],
        'rework_reason': row['rework_reason'],
        'last_gate_actor': row['last_gate_actor'],
        'last_gate_decision_at': row['last_gate_decision_at'],
        'auto_close_policy': row['auto_close_policy'],
        'summary': row['summary'],
        'created_at': row['created_at'],
        'dispatched_at': row['dispatched_at'],
        'ack_at': row['ack_at'],
        'completed_at': row['completed_at'],
        'review_completed_at': row['review_completed_at'],
        'verify_completed_at': row['verify_completed_at'],
        'current_status_at': row['current_status_at'],
        'review_state': row['review_state'],
        'verify_ok': None if row['verify_ok'] is None else bool(row['verify_ok']),
        'write_scope': write_scope,
        'artifacts': artifacts,
        'task_dir': row['task_dir'],
        'task_json_path': row['task_json_path'],
        'last_synced_at': row['last_synced_at'],
        'active_work_seconds': active_work_seconds,
        'persisted_stage_durations': _persisted_stage_durations_from_row(row),
    }


def _row_to_task_event(row: sqlite3.Row) -> dict[str, Any]:
    payload = json.loads(row['payload_json'] or '{}')
    happened_at = row['event_at'] or row['observed_at']
    return {
        'event_id': row['event_key'],
        'event_kind': 'task_event',
        'task_id': row['task_id'],
        'event_type': row['event_type'],
        'source': row['source'],
        'status_from': row['status_from'],
        'status_to': row['status_to'],
        'artifact_path': row['artifact_path'],
        'happened_at': happened_at,
        'observed_at': row['observed_at'],
        'payload': payload,
        'summary': payload.get('reason') or payload.get('summary') or payload.get('status'),
    }


def _row_to_communication_event(row: sqlite3.Row) -> dict[str, Any]:
    payload = json.loads(row['payload_json'] or '{}')
    return {
        'event_id': row['event_id'],
        'event_kind': 'communication',
        'task_id': row['task_id'],
        'thread_id': row['thread_id'],
        'channel': row['channel'],
        'event_type': row['event_type'],
        'event_class': row['event_class'],
        'source_type': row['source_type'],
        'from_actor': row['from_actor'],
        'to_actor': row['to_actor'],
        'priority': row['priority'],
        'severity': row['severity'],
        'message_text': row['message_text'],
        'reply_to': row['reply_to'],
        'source_file': row['source_file'],
        'source_line': row['source_line'],
        'source_msg_id': row['source_msg_id'],
        'source_name': row['source_name'],
        'related_artifact_path': row['related_artifact_path'],
        'happened_at': row['happened_at'],
        'observed_at': row['observed_at'],
        'payload': payload,
    }


def _fetch_tasks(
    conn: sqlite3.Connection,
    *,
    project: str | None = None,
    agent: str | None = None,
    board_status: str | None = None,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    values: list[Any] = []
    if project:
        clauses.append('project = ?')
        values.append(project)
    if agent:
        clauses.append('assigned_agent = ?')
        values.append(agent)
    if board_status:
        clauses.append('board_status = ?')
        values.append(board_status)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ''
    rows = conn.execute(
        f'''
        SELECT tasks.*,
               task_stage_durations.create_to_dispatch_seconds,
               task_stage_durations.dispatch_to_ack_seconds,
               task_stage_durations.ack_to_result_seconds,
               task_stage_durations.result_to_review_seconds,
               task_stage_durations.review_to_verify_seconds,
               task_stage_durations.verify_to_close_seconds,
               task_stage_durations.total_cycle_seconds
        FROM tasks
        LEFT JOIN task_stage_durations ON task_stage_durations.task_id = tasks.task_id
        {where}
        ORDER BY COALESCE(tasks.current_status_at, tasks.updated_at, tasks.created_at) DESC, tasks.task_id ASC
        ''',
        values,
    ).fetchall()
    tasks = [_row_to_task(row) for row in rows]
    if not tasks:
        return []
    task_ids = [task['task_id'] for task in tasks]
    placeholders = ','.join('?' for _ in task_ids)
    counts = {
        row['task_id']: row['comm_count']
        for row in conn.execute(
            f'''
            SELECT task_id, COUNT(*) AS comm_count
            FROM communication_events
            WHERE task_id IN ({placeholders})
            GROUP BY task_id
            ''',
            task_ids,
        ).fetchall()
    }
    for task in tasks:
        task['communication_count'] = int(counts.get(task['task_id'], 0))
    return tasks


def _fetch_single_task(conn: sqlite3.Connection, task_id: str) -> dict[str, Any] | None:
    rows = conn.execute('''SELECT tasks.*, task_stage_durations.create_to_dispatch_seconds, task_stage_durations.dispatch_to_ack_seconds, task_stage_durations.ack_to_result_seconds, task_stage_durations.result_to_review_seconds, task_stage_durations.review_to_verify_seconds, task_stage_durations.verify_to_close_seconds, task_stage_durations.total_cycle_seconds FROM tasks LEFT JOIN task_stage_durations ON task_stage_durations.task_id = tasks.task_id WHERE tasks.task_id = ? LIMIT 1''', (task_id,)).fetchall()
    if not rows:
        return None
    task = _row_to_task(rows[0])
    task['communication_count'] = conn.execute(
        'SELECT COUNT(*) FROM communication_events WHERE task_id = ?',
        (task_id,),
    ).fetchone()[0]
    return task


def _fetch_task_events(conn: sqlite3.Connection, task_id: str) -> list[dict[str, Any]]:
    rows = conn.execute(
        '''
        SELECT *
        FROM task_events
        WHERE task_id = ?
        ORDER BY COALESCE(event_at, observed_at) ASC, event_key ASC
        ''',
        (task_id,),
    ).fetchall()
    return [_row_to_task_event(row) for row in rows]


def fetch_communication_events(
    conn: sqlite3.Connection,
    *,
    task_id: str | None = None,
    agent_id: str | None = None,
    start_at: str | None = None,
    end_at: str | None = None,
    limit: int | None = None,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    values: list[Any] = []
    if task_id:
        clauses.append('task_id = ?')
        values.append(task_id)
    if agent_id:
        clauses.append('(from_actor = ? OR to_actor = ?)')
        values.extend([agent_id, agent_id])
    if start_at:
        clauses.append('COALESCE(happened_at, observed_at) >= ?')
        values.append(start_at)
    if end_at:
        clauses.append('COALESCE(happened_at, observed_at) <= ?')
        values.append(end_at)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ''
    sql = f'''
        SELECT *
        FROM communication_events
        {where}
        ORDER BY COALESCE(happened_at, observed_at) ASC, event_id ASC
    '''
    if limit is not None:
        sql += f' LIMIT {max(int(limit), 1)}'
    rows = conn.execute(sql, values).fetchall()
    return [_row_to_communication_event(row) for row in rows]


def _build_stage_durations(task: dict[str, Any]) -> dict[str, Any]:
    persisted = dict(task.get('persisted_stage_durations') or {})
    computed = {
        'create_to_dispatch_seconds': _seconds_between(task.get('created_at'), task.get('dispatched_at')),
        'dispatch_to_ack_seconds': _seconds_between(task.get('dispatched_at'), task.get('ack_at')),
        'ack_to_result_seconds': _seconds_between(task.get('ack_at'), task.get('completed_at')),
        'result_to_review_seconds': _seconds_between(task.get('completed_at'), task.get('review_completed_at')),
        'review_to_verify_seconds': _seconds_between(task.get('review_completed_at'), task.get('verify_completed_at')),
        'verify_to_close_seconds': _seconds_between(task.get('verify_completed_at'), task.get('current_status_at')),
        'total_cycle_seconds': _seconds_between(task.get('created_at'), task.get('current_status_at')),
    }
    durations = {key: persisted.get(key) if persisted.get(key) is not None else computed.get(key) for key in computed}
    durations_hours = {
        key.replace('_seconds', '_hours'): _duration_hours(value)
        for key, value in durations.items()
    }
    return {**durations, **durations_hours}


def _merge_timelines(task_events: list[dict[str, Any]], communication_events: list[dict[str, Any]]) -> list[dict[str, Any]]:
    merged = [*task_events, *communication_events]

    def _sort_key(item: dict[str, Any]):
        ts = item.get('happened_at') or item.get('observed_at') or ''
        return (ts, item.get('event_kind') or '', item.get('event_id') or '')

    merged.sort(key=_sort_key)
    return merged


def build_task_detail_payload(conn: sqlite3.Connection, task_id: str) -> dict[str, Any]:
    task = _fetch_single_task(conn, task_id)
    if task is None:
        return {
            'generated_at': _now_iso(),
            'task': None,
            'status_timeline': [],
            'communication_timeline': [],
            'timeline': [],
            'durations': {},
        }
    status_timeline = _fetch_task_events(conn, task_id)
    communication_timeline = fetch_communication_events(conn, task_id=task_id)
    return {
        'generated_at': _now_iso(),
        'task': task,
        'status_timeline': status_timeline,
        'communication_timeline': communication_timeline,
        'timeline': _merge_timelines(status_timeline, communication_timeline),
        'durations': _build_stage_durations(task),
    }


def build_task_timeline_payload(conn: sqlite3.Connection, task_id: str) -> dict[str, Any]:
    payload = build_task_detail_payload(conn, task_id)
    if payload.get('task') is None:
        return {
            'generated_at': payload['generated_at'],
            'task': None,
            'status_timeline': [],
            'communication_timeline': [],
            'timeline': [],
        }
    return {
        'generated_at': payload['generated_at'],
        'task': payload['task'],
        'status_timeline': payload['status_timeline'],
        'communication_timeline': payload['communication_timeline'],
        'timeline': payload['timeline'],
    }


def build_task_communications_payload(conn: sqlite3.Connection, task_id: str) -> dict[str, Any]:
    task = _fetch_single_task(conn, task_id)
    if task is None:
        return {
            'generated_at': _now_iso(),
            'task': None,
            'communications': [],
        }
    communications = fetch_communication_events(conn, task_id=task_id)
    return {
        'generated_at': _now_iso(),
        'task': task,
        'communications': communications,
    }


def build_board_payload(
    conn: sqlite3.Connection,
    *,
    project: str | None = None,
    agent: str | None = None,
) -> dict[str, Any]:
    tasks = _fetch_tasks(conn, project=project, agent=agent)
    gate_counts: dict[str, int] = defaultdict(int)
    column_order = ['pending', 'working', 'ready_for_merge', 'blocked', 'done']
    columns = {
        key: {
            'key': key,
            'label': key,
            'count': 0,
            'tasks': [],
        }
        for key in column_order
    }
    for task in tasks:
        if task.get('merge_gate_state'):
            gate_counts[str(task['merge_gate_state'])] += 1
        column = columns.setdefault(
            task['board_status'],
            {'key': task['board_status'], 'label': task['board_status'], 'count': 0, 'tasks': []},
        )
        column['tasks'].append(task)
        column['count'] += 1
    extra_keys = [key for key in columns if key not in column_order]
    ordered_columns = [columns[key] for key in column_order if key in columns] + [columns[key] for key in extra_keys]
    return {
        'generated_at': _now_iso(),
        'filters': {'project': project, 'agent': agent},
        'summary': {
            'task_count': len(tasks),
            'column_counts': {key: columns[key]['count'] for key in columns},
            'merge_gate_counts': dict(gate_counts),
        },
        'columns': ordered_columns,
    }


def build_gantt_payload(
    conn: sqlite3.Connection,
    *,
    project: str | None = None,
    agent: str | None = None,
) -> dict[str, Any]:
    tasks = _fetch_tasks(conn, project=project, agent=agent)
    generated_at = _now_iso()
    items: list[dict[str, Any]] = []
    for task in tasks:
        milestone_created = task['created_at']
        milestone_dispatched = task['dispatched_at'] or task['created_at']
        milestone_ack = task['ack_at'] or task['dispatched_at'] or task['created_at']
        milestone_completed = task['completed_at']
        milestone_review = task['review_completed_at']
        milestone_verify = task['verify_completed_at']
        span_start = milestone_ack or milestone_dispatched or milestone_created
        span_end = milestone_review or milestone_verify or milestone_completed or (
            generated_at if task['board_status'] in {'pending', 'working', 'blocked'} else task['current_status_at']
        )
        items.append({
            'task_id': task['task_id'],
            'title': task['title'],
            'project': task['project'],
            'assigned_agent': task['assigned_agent'],
            'current_status': task['current_status'],
            'board_status': task['board_status'],
            'display_start_at': span_start,
            'display_end_at': span_end,
            'duration_seconds': _seconds_between(span_start, span_end),
            'communication_count': task.get('communication_count', 0),
            'milestones': {
                'created': milestone_created,
                'dispatched': milestone_dispatched,
                'ack': milestone_ack,
                'completed': milestone_completed,
                'review_completed': milestone_review,
                'verify_completed': milestone_verify,
                'current_status': task['current_status_at'],
            },
        })
    return {
        'generated_at': generated_at,
        'filters': {'project': project, 'agent': agent},
        'items': items,
    }


def build_agent_stats_payload(conn: sqlite3.Connection, *, project: str | None = None) -> dict[str, Any]:
    tasks = _fetch_tasks(conn, project=project)
    generated_at = _now_iso()
    agents: dict[str, dict[str, Any]] = {}
    for task in tasks:
        agent_id = task['assigned_agent'] or 'unassigned'
        agent_entry = agents.setdefault(
            agent_id,
            {
                'agent_id': agent_id,
                'project': project,
                'active_task_count': 0,
                'blocked_task_count': 0,
                'ready_for_merge_count': 0,
                'completed_task_count': 0,
                'current_load_count': 0,
                'total_tracked_work_seconds': 0.0,
                'total_communication_count': 0,
                'active_tasks': [],
            },
        )
        agent_entry['total_communication_count'] += int(task.get('communication_count', 0))
        if task['current_status'] in ACTIVE_LOAD_STATUSES:
            agent_entry['active_task_count'] += 1
            agent_entry['current_load_count'] += 1
            agent_entry['active_tasks'].append({
                'task_id': task['task_id'],
                'title': task['title'],
                'current_status': task['current_status'],
                'board_status': task['board_status'],
            })
        if task['current_status'] == 'blocked':
            agent_entry['blocked_task_count'] += 1
        if task['current_status'] == 'ready_for_merge':
            agent_entry['ready_for_merge_count'] += 1
        if task['completed_at']:
            agent_entry['completed_task_count'] += 1
        if task['active_work_seconds'] is not None:
            agent_entry['total_tracked_work_seconds'] += task['active_work_seconds']
    return {
        'generated_at': generated_at,
        'filters': {'project': project},
        'summary': {
            'agent_count': len(agents),
            'total_active_tasks': sum(agent['active_task_count'] for agent in agents.values()),
        },
        'agents': sorted(agents.values(), key=lambda item: (-item['current_load_count'], item['agent_id'])),
    }


def build_health_payload(conn: sqlite3.Connection, *, db_path: str) -> dict[str, Any]:
    task_count = conn.execute('SELECT COUNT(*) FROM tasks').fetchone()[0]
    event_count = conn.execute('SELECT COUNT(*) FROM task_events').fetchone()[0]
    communication_count = conn.execute('SELECT COUNT(*) FROM communication_events').fetchone()[0]
    last_synced_at = conn.execute('SELECT MAX(last_synced_at) FROM tasks').fetchone()[0]
    status_rows = conn.execute(
        'SELECT board_status, COUNT(*) AS count FROM tasks GROUP BY board_status ORDER BY board_status'
    ).fetchall()
    return {
        'status': 'ok',
        'generated_at': _now_iso(),
        'db_path': db_path,
        'task_count': task_count,
        'event_count': event_count,
        'communication_event_count': communication_count,
        'last_synced_at': last_synced_at,
        'board_status_counts': {row['board_status']: row['count'] for row in status_rows},
    }


def fetch_task_metrics_daily(
    conn: sqlite3.Connection,
    *,
    project: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    values: list[Any] = []
    project_key = project or '__all__'
    clauses.append('project = ?')
    values.append(project_key)
    if start_date:
        clauses.append('metric_date >= ?')
        values.append(start_date)
    if end_date:
        clauses.append('metric_date <= ?')
        values.append(end_date)
    where = f"WHERE {' AND '.join(clauses)}"
    sql = (
        'SELECT * FROM task_metrics_daily '
        + where
        + ' ORDER BY metric_date ASC'
    )
    rows = conn.execute(sql, values).fetchall()
    return [dict(row) for row in rows]


def fetch_agent_metrics_daily(
    conn: sqlite3.Connection,
    *,
    project: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> list[dict[str, Any]]:
    clauses: list[str] = []
    values: list[Any] = []
    project_key = project or '__all__'
    clauses.append('project = ?')
    values.append(project_key)
    if start_date:
        clauses.append('metric_date >= ?')
        values.append(start_date)
    if end_date:
        clauses.append('metric_date <= ?')
        values.append(end_date)
    where = f"WHERE {' AND '.join(clauses)}"
    sql = (
        'SELECT * FROM agent_metrics_daily '
        + where
        + ' ORDER BY metric_date ASC, agent_id ASC'
    )
    rows = conn.execute(sql, values).fetchall()
    return [dict(row) for row in rows]


def build_daily_metrics_payload(
    conn: sqlite3.Connection,
    *,
    project: str | None = None,
    start_date: str | None = None,
    end_date: str | None = None,
) -> dict[str, Any]:
    task_metrics = fetch_task_metrics_daily(conn, project=project, start_date=start_date, end_date=end_date)
    agent_metrics = fetch_agent_metrics_daily(conn, project=project, start_date=start_date, end_date=end_date)
    return {
        'generated_at': _now_iso(),
        'filters': {
            'project': project or '__all__',
            'start_date': start_date,
            'end_date': end_date,
        },
        'task_metrics': task_metrics,
        'agent_metrics': agent_metrics,
    }


def _aggregate_label(field: str, value: Any) -> str:
    normalized = str(value).strip() if value not in (None, '') else ''
    if normalized:
        return normalized
    if field == 'parent_task_id':
        return '(root task)'
    return '(none)'


def _aggregate_count_map(tasks: list[dict[str, Any]], field: str) -> dict[str, int]:
    counts: dict[str, int] = {}
    for task in tasks:
        label = _aggregate_label(field, task.get(field))
        counts[label] = counts.get(label, 0) + 1
    return dict(sorted(counts.items(), key=lambda item: (-item[1], item[0])))


def _load_task_json_metadata(task: dict[str, Any], cache: dict[str, dict[str, Any]]) -> dict[str, Any]:
    task_json_path = task.get('task_json_path')
    if not task_json_path:
        return {}
    cached = cache.get(task_json_path)
    if cached is not None:
        return cached
    path = Path(task_json_path)
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
        if not isinstance(payload, dict):
            payload = {}
    except (OSError, json.JSONDecodeError):
        payload = {}
    cache[task_json_path] = payload
    return payload


def _coalesce_task_field(task: dict[str, Any], metadata: dict[str, Any], field: str) -> Any:
    value = task.get(field)
    if value not in (None, ''):
        return value
    metadata_value = metadata.get(field)
    if isinstance(metadata_value, str):
        metadata_value = metadata_value.strip()
    return metadata_value if metadata_value not in ('',) else None


def _task_sort_key(task: dict[str, Any]) -> tuple[str, str]:
    return (
        task.get('current_status_at') or task.get('completed_at') or task.get('created_at') or '',
        task.get('task_id') or '',
    )


def _build_aggregate_task(task: dict[str, Any], metadata: dict[str, Any]) -> dict[str, Any]:
    return {
        'task_id': task.get('task_id'),
        'title': task.get('title'),
        'project': task.get('project'),
        'owner_pm': _coalesce_task_field(task, metadata, 'owner_pm'),
        'domain': _coalesce_task_field(task, metadata, 'domain'),
        'task_level': _coalesce_task_field(task, metadata, 'task_level'),
        'parent_task_id': _coalesce_task_field(task, metadata, 'parent_task_id'),
        'root_request_id': _coalesce_task_field(task, metadata, 'root_request_id'),
        'assigned_agent': task.get('assigned_agent'),
        'reviewer': task.get('reviewer'),
        'current_status': task.get('current_status'),
        'board_status': task.get('board_status'),
        'summary': task.get('summary'),
        'created_at': task.get('created_at'),
        'dispatched_at': task.get('dispatched_at'),
        'ack_at': task.get('ack_at'),
        'completed_at': task.get('completed_at'),
        'review_completed_at': task.get('review_completed_at'),
        'verify_completed_at': task.get('verify_completed_at'),
        'current_status_at': task.get('current_status_at'),
        'communication_count': int(task.get('communication_count', 0) or 0),
        'task_json_path': task.get('task_json_path'),
        'task_dir': task.get('task_dir'),
        'last_synced_at': task.get('last_synced_at'),
    }


def _matches_aggregate_filter(field: str, actual: Any, expected: str | None) -> bool:
    if expected in (None, ''):
        return True
    normalized_actual = actual.strip() if isinstance(actual, str) else actual
    if field == 'parent_task_id' and expected in {'__root__', '(root task)', 'root'}:
        return normalized_actual in (None, '')
    return normalized_actual == expected


def _filter_aggregate_tasks(
    tasks: list[dict[str, Any]],
    *,
    owner_pm: str | None = None,
    domain: str | None = None,
    task_level: str | None = None,
    parent_task_id: str | None = None,
    root_request_id: str | None = None,
) -> list[dict[str, Any]]:
    filtered: list[dict[str, Any]] = []
    for task in tasks:
        if not _matches_aggregate_filter('owner_pm', task.get('owner_pm'), owner_pm):
            continue
        if not _matches_aggregate_filter('domain', task.get('domain'), domain):
            continue
        if not _matches_aggregate_filter('task_level', task.get('task_level'), task_level):
            continue
        if not _matches_aggregate_filter('parent_task_id', task.get('parent_task_id'), parent_task_id):
            continue
        if not _matches_aggregate_filter('root_request_id', task.get('root_request_id'), root_request_id):
            continue
        filtered.append(task)
    return filtered


def _summarize_aggregate_tasks(tasks: list[dict[str, Any]]) -> dict[str, Any]:
    return {
        'task_count': len(tasks),
        'blocked_count': sum(
            1
            for task in tasks
            if task.get('current_status') in BLOCKED_AGGREGATE_STATUSES or task.get('board_status') == 'blocked'
        ),
        'active_count': sum(
            1
            for task in tasks
            if task.get('current_status') in ACTIVE_LOAD_STATUSES or task.get('board_status') in {'pending', 'working', 'blocked'}
        ),
        'ready_for_merge_count': sum(
            1
            for task in tasks
            if task.get('current_status') == 'ready_for_merge' or task.get('board_status') == 'ready_for_merge'
        ),
        'done_count': sum(1 for task in tasks if task.get('board_status') == 'done'),
        'current_status_counts': _aggregate_count_map(tasks, 'current_status'),
        'board_status_counts': _aggregate_count_map(tasks, 'board_status'),
        'owner_pm_counts': _aggregate_count_map(tasks, 'owner_pm'),
        'domain_counts': _aggregate_count_map(tasks, 'domain'),
        'task_level_counts': _aggregate_count_map(tasks, 'task_level'),
    }


def _build_aggregate_groups(tasks: list[dict[str, Any]], field: str) -> list[dict[str, Any]]:
    grouped: dict[tuple[Any, str], list[dict[str, Any]]] = defaultdict(list)
    for task in tasks:
        raw_key = task.get(field)
        grouped[(raw_key, _aggregate_label(field, raw_key))].append(task)

    entries: list[dict[str, Any]] = []
    for (raw_key, label), group_tasks in grouped.items():
        ordered = sorted(group_tasks, key=_task_sort_key, reverse=True)
        entries.append({
            'key': raw_key,
            'label': label,
            **_summarize_aggregate_tasks(ordered),
            'task_ids': [task['task_id'] for task in ordered],
        })
    return sorted(entries, key=lambda item: (-item['task_count'], item['label']))


def _build_request_trees(tasks: list[dict[str, Any]]) -> list[dict[str, Any]]:
    grouped: dict[tuple[Any, str], list[dict[str, Any]]] = defaultdict(list)
    for task in tasks:
        raw_root = task.get('root_request_id')
        grouped[(raw_root, _aggregate_label('root_request_id', raw_root))].append(task)

    trees: list[dict[str, Any]] = []
    for (raw_root, label), root_tasks in grouped.items():
        ordered = sorted(root_tasks, key=_task_sort_key, reverse=True)
        parents: dict[tuple[Any, str], list[dict[str, Any]]] = defaultdict(list)
        for task in ordered:
            raw_parent = task.get('parent_task_id')
            parents[(raw_parent, _aggregate_label('parent_task_id', raw_parent))].append(task)

        parent_groups: list[dict[str, Any]] = []
        for (raw_parent, parent_label), parent_tasks in parents.items():
            parent_groups.append({
                'parent_task_id': raw_parent,
                'label': parent_label,
                **_summarize_aggregate_tasks(parent_tasks),
                'task_ids': [task['task_id'] for task in parent_tasks],
            })

        trees.append({
            'root_request_id': raw_root,
            'label': label,
            **_summarize_aggregate_tasks(ordered),
            'task_ids': [task['task_id'] for task in ordered],
            'root_task_ids': [task['task_id'] for task in ordered if not task.get('parent_task_id')],
            'parent_group_count': len(parent_groups),
            'parent_groups': sorted(parent_groups, key=lambda item: (-item['task_count'], item['label'])),
        })

    return sorted(trees, key=lambda item: (-item['task_count'], item['label']))


def build_task_aggregate_payload(
    conn: sqlite3.Connection,
    *,
    project: str | None = None,
    owner_pm: str | None = None,
    domain: str | None = None,
    task_level: str | None = None,
    parent_task_id: str | None = None,
    root_request_id: str | None = None,
) -> dict[str, Any]:
    metadata_cache: dict[str, dict[str, Any]] = {}
    tasks = [
        _build_aggregate_task(task, _load_task_json_metadata(task, metadata_cache))
        for task in _fetch_tasks(conn, project=project)
    ]
    filtered = _filter_aggregate_tasks(
        tasks,
        owner_pm=owner_pm,
        domain=domain,
        task_level=task_level,
        parent_task_id=parent_task_id,
        root_request_id=root_request_id,
    )
    ordered = sorted(filtered, key=_task_sort_key, reverse=True)
    last_synced_at = max((task.get('last_synced_at') for task in ordered if task.get('last_synced_at')), default=None)
    return {
        'generated_at': _now_iso(),
        'read_only': True,
        'source': {
            'kind': 'task_aggregate_view',
            'fact_source': 'dashboard tasks read model',
            'hierarchy_enrichment': 'task_level falls back to task.json when the SQLite snapshot does not persist that field',
            'note': 'This payload is derived for inspection only and must not be treated as task status source of truth.',
        },
        'filters': {
            'project': project,
            'owner_pm': owner_pm,
            'domain': domain,
            'task_level': task_level,
            'parent_task_id': parent_task_id,
            'root_request_id': root_request_id,
        },
        'summary': {
            **_summarize_aggregate_tasks(ordered),
            'dimension_order': list(READ_ONLY_AGGREGATE_DIMENSIONS),
            'last_synced_at': last_synced_at,
        },
        'tasks': ordered,
        'groupings': {
            field: _build_aggregate_groups(ordered, field)
            for field in READ_ONLY_AGGREGATE_DIMENSIONS
        },
        'request_trees': _build_request_trees(ordered),
    }
