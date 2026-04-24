from __future__ import annotations

import json
import sqlite3
from datetime import datetime, timezone
from typing import Any

ACTIVE_LOAD_STATUSES = {'pending', 'dispatched', 'working', 'blocked'}


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
        'current_status': row['current_status'],
        'board_status': row['board_status'],
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
        'last_synced_at': row['last_synced_at'],
        'active_work_seconds': active_work_seconds,
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
        SELECT *
        FROM tasks
        {where}
        ORDER BY COALESCE(current_status_at, updated_at, created_at) DESC, task_id ASC
        ''',
        values,
    ).fetchall()
    return [_row_to_task(row) for row in rows]


def build_board_payload(
    conn: sqlite3.Connection,
    *,
    project: str | None = None,
    agent: str | None = None,
) -> dict[str, Any]:
    tasks = _fetch_tasks(conn, project=project, agent=agent)
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
                'active_tasks': [],
            },
        )
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
        'last_synced_at': last_synced_at,
        'board_status_counts': {row['board_status']: row['count'] for row in status_rows},
    }
