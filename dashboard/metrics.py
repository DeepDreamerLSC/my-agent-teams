from __future__ import annotations

import sqlite3
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, time, timedelta, timezone
from typing import Any, Iterable

from .db import (
    connect_db,
    resolve_db_path,
    upsert_agent_metric_daily,
    upsert_task_metric_daily,
    utcnow_iso,
)

BLOCKED_STATUSES = {'blocked', 'failed', 'cancelled', 'timeout'}
ACTIVE_WORK_STATUSES = {'pending', 'dispatched', 'working', 'blocked'}
ALL_PROJECT_KEY = '__all__'
_TASK_TIME_FIELDS = (
    'created_at',
    'dispatched_at',
    'ack_at',
    'completed_at',
    'review_completed_at',
    'verify_completed_at',
    'current_status_at',
)


@dataclass(frozen=True)
class TaskSnapshot:
    task_id: str
    project: str
    assigned_agent: str
    current_status: str | None
    created_at: str | None
    dispatched_at: str | None
    ack_at: str | None
    completed_at: str | None
    review_completed_at: str | None
    verify_completed_at: str | None
    current_status_at: str | None


def _parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone()
    except ValueError:
        return None


def _seconds_between(start: datetime | None, end: datetime | None) -> float | None:
    if start is None or end is None:
        return None
    return max((end - start).total_seconds(), 0.0)


def _normalize_project(value: Any) -> str:
    project = str(value or '').strip()
    return project or 'unknown'


def _normalize_agent(value: Any) -> str:
    agent = str(value or '').strip()
    return agent or 'unassigned'


def _coalesce_dt(*values: str | None) -> datetime | None:
    for value in values:
        parsed = _parse_dt(value)
        if parsed is not None:
            return parsed
    return None


def _task_active_window(task: TaskSnapshot) -> tuple[datetime | None, datetime | None]:
    start = _coalesce_dt(task.ack_at, task.dispatched_at, task.created_at)
    end = _coalesce_dt(task.completed_at, task.current_status_at)
    return start, end


def _overlap_seconds(window_start: datetime | None, window_end: datetime | None, day_start: datetime, day_end: datetime) -> float:
    if window_start is None:
        return 0.0
    effective_end = window_end or day_end
    start = max(window_start, day_start)
    end = min(effective_end, day_end)
    if end <= start:
        return 0.0
    return (end - start).total_seconds()


def _date_range(start_date: date, end_date: date) -> Iterable[date]:
    current = start_date
    while current <= end_date:
        yield current
        current += timedelta(days=1)


def _task_touched_on_day(task: TaskSnapshot, metric_day: date) -> bool:
    for field in _TASK_TIME_FIELDS:
        parsed = _parse_dt(getattr(task, field))
        if parsed and parsed.date() == metric_day:
            return True
    return False


def _is_on_day(value: str | None, metric_day: date) -> bool:
    parsed = _parse_dt(value)
    return bool(parsed and parsed.date() == metric_day)


def _fetch_tasks(conn: sqlite3.Connection, *, project: str | None = None) -> list[TaskSnapshot]:
    clauses: list[str] = []
    values: list[Any] = []
    if project and project != ALL_PROJECT_KEY:
        clauses.append('project = ?')
        values.append(project)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ''
    rows = conn.execute(
        f'''
        SELECT task_id, project, assigned_agent, current_status,
               created_at, dispatched_at, ack_at, completed_at,
               review_completed_at, verify_completed_at, current_status_at
        FROM tasks
        {where}
        ORDER BY task_id ASC
        ''',
        values,
    ).fetchall()
    return [
        TaskSnapshot(
            task_id=row['task_id'],
            project=_normalize_project(row['project']),
            assigned_agent=_normalize_agent(row['assigned_agent']),
            current_status=row['current_status'],
            created_at=row['created_at'],
            dispatched_at=row['dispatched_at'],
            ack_at=row['ack_at'],
            completed_at=row['completed_at'],
            review_completed_at=row['review_completed_at'],
            verify_completed_at=row['verify_completed_at'],
            current_status_at=row['current_status_at'],
        )
        for row in rows
    ]


def _resolve_rebuild_range(tasks: list[TaskSnapshot], *, start_date: date | None, end_date: date | None) -> tuple[date, date]:
    if start_date and end_date:
        return start_date, end_date
    dates: list[date] = []
    for task in tasks:
        for field in _TASK_TIME_FIELDS:
            parsed = _parse_dt(getattr(task, field))
            if parsed is not None:
                dates.append(parsed.date())
    today = datetime.now(timezone.utc).astimezone().date()
    if not dates:
        return start_date or today, end_date or today
    return start_date or min(dates), end_date or max(dates)


def _build_task_metric_record(metric_date: date, project: str, tasks: list[TaskSnapshot]) -> dict[str, Any]:
    touched_tasks = [task for task in tasks if _task_touched_on_day(task, metric_date)]
    created_tasks = [task for task in tasks if _is_on_day(task.created_at, metric_date)]
    completed_tasks = [task for task in tasks if _is_on_day(task.completed_at, metric_date)]
    blocked_tasks = [
        task for task in tasks
        if task.current_status in BLOCKED_STATUSES and _is_on_day(task.current_status_at, metric_date)
    ]
    cycle_durations = [
        seconds for task in completed_tasks
        if (seconds := _seconds_between(_parse_dt(task.created_at), _parse_dt(task.completed_at))) is not None
    ]
    ack_result_durations = [
        seconds for task in completed_tasks
        if (seconds := _seconds_between(_parse_dt(task.ack_at), _parse_dt(task.completed_at))) is not None
    ]
    touched_count = len({task.task_id for task in touched_tasks})
    completed_count = len(completed_tasks)
    blocked_count = len(blocked_tasks)
    return {
        'metric_date': metric_date.isoformat(),
        'project': project,
        'created_task_count': len(created_tasks),
        'completed_task_count': completed_count,
        'blocked_task_count': blocked_count,
        'touched_task_count': touched_count,
        'completion_rate': round(completed_count / touched_count, 4) if touched_count else None,
        'blocked_rate': round(blocked_count / touched_count, 4) if touched_count else None,
        'avg_cycle_seconds': round(sum(cycle_durations) / len(cycle_durations), 3) if cycle_durations else None,
        'avg_ack_to_result_seconds': round(sum(ack_result_durations) / len(ack_result_durations), 3) if ack_result_durations else None,
        'updated_at': utcnow_iso(),
    }



def _build_agent_metric_records(metric_date: date, project: str, tasks: list[TaskSnapshot]) -> list[dict[str, Any]]:
    day_start = datetime.combine(metric_date, time.min, tzinfo=datetime.now(timezone.utc).astimezone().tzinfo)
    day_end = day_start + timedelta(days=1)
    grouped: dict[str, dict[str, Any]] = defaultdict(lambda: {
        'active_task_count': 0,
        'blocked_task_count': 0,
        'ready_for_merge_count': 0,
        'completed_task_count': 0,
        'total_tracked_work_seconds': 0.0,
    })
    for task in tasks:
        agent_key = task.assigned_agent
        active_start, active_end = _task_active_window(task)
        overlap = _overlap_seconds(active_start, active_end, day_start, day_end)
        if overlap > 0:
            grouped[agent_key]['active_task_count'] += 1
            grouped[agent_key]['total_tracked_work_seconds'] += overlap
        if task.current_status in BLOCKED_STATUSES and _is_on_day(task.current_status_at, metric_date):
            grouped[agent_key]['blocked_task_count'] += 1
        if task.current_status == 'ready_for_merge' and _is_on_day(task.current_status_at, metric_date):
            grouped[agent_key]['ready_for_merge_count'] += 1
        if _is_on_day(task.completed_at, metric_date):
            grouped[agent_key]['completed_task_count'] += 1
    records: list[dict[str, Any]] = []
    for agent_id, payload in sorted(grouped.items()):
        active_count = int(payload['active_task_count'])
        total_seconds = float(payload['total_tracked_work_seconds'])
        records.append({
            'metric_date': metric_date.isoformat(),
            'project': project,
            'agent_id': agent_id,
            'active_task_count': active_count,
            'blocked_task_count': int(payload['blocked_task_count']),
            'ready_for_merge_count': int(payload['ready_for_merge_count']),
            'completed_task_count': int(payload['completed_task_count']),
            'total_tracked_work_seconds': round(total_seconds, 3),
            'avg_active_work_seconds': round(total_seconds / active_count, 3) if active_count else None,
            'updated_at': utcnow_iso(),
        })
    return records


def rebuild_daily_metrics(
    db_path: str | Path | None = None,
    *,
    start_date: date | None = None,
    end_date: date | None = None,
    project: str | None = None,
) -> dict[str, Any]:
    conn = connect_db(db_path)
    try:
        tasks = _fetch_tasks(conn, project=project)
        resolved_start, resolved_end = _resolve_rebuild_range(tasks, start_date=start_date, end_date=end_date)
        projects = sorted({_normalize_project(task.project) for task in tasks}) if not project else [project]
        if not project and ALL_PROJECT_KEY not in projects:
            projects.insert(0, ALL_PROJECT_KEY)
        task_rows = 0
        agent_rows = 0
        with conn:
            if project:
                conn.execute('DELETE FROM task_metrics_daily WHERE project = ? AND metric_date BETWEEN ? AND ?', (project, resolved_start.isoformat(), resolved_end.isoformat()))
                conn.execute('DELETE FROM agent_metrics_daily WHERE project = ? AND metric_date BETWEEN ? AND ?', (project, resolved_start.isoformat(), resolved_end.isoformat()))
            else:
                conn.execute('DELETE FROM task_metrics_daily WHERE metric_date BETWEEN ? AND ?', (resolved_start.isoformat(), resolved_end.isoformat()))
                conn.execute('DELETE FROM agent_metrics_daily WHERE metric_date BETWEEN ? AND ?', (resolved_start.isoformat(), resolved_end.isoformat()))
            for metric_day in _date_range(resolved_start, resolved_end):
                for project_key in projects:
                    scoped_tasks = tasks if project_key == ALL_PROJECT_KEY else [task for task in tasks if task.project == project_key]
                    task_record = _build_task_metric_record(metric_day, project_key, scoped_tasks)
                    upsert_task_metric_daily(conn, task_record)
                    task_rows += 1
                    for agent_record in _build_agent_metric_records(metric_day, project_key, scoped_tasks):
                        upsert_agent_metric_daily(conn, agent_record)
                        agent_rows += 1
        return {
            'db_path': str(resolve_db_path(db_path)),
            'project': project,
            'start_date': resolved_start.isoformat(),
            'end_date': resolved_end.isoformat(),
            'task_metric_rows': task_rows,
            'agent_metric_rows': agent_rows,
            'projects': projects,
            'task_count_considered': len(tasks),
        }
    finally:
        conn.close()
