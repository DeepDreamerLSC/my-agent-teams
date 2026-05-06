#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE_ROOT = SCRIPT_DIR.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from dashboard.db import connect_db
from dashboard.ingest import backfill_tasks
from dashboard.query import build_task_aggregate_payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Render read-only task aggregate summaries for PM inspection.')
    parser.add_argument('--db', default=None)
    parser.add_argument('--project', default=None)
    parser.add_argument('--owner-pm', default=None)
    parser.add_argument('--domain', default=None)
    parser.add_argument('--task-level', default=None)
    parser.add_argument('--parent-task-id', default=None)
    parser.add_argument('--root-request-id', default=None)
    parser.add_argument('--group-limit', type=int, default=10)
    parser.add_argument('--json', action='store_true', help='Print full JSON payload')
    parser.add_argument('--sync-first', action='store_true', help='Backfill tasks/ into SQLite before aggregating')
    parser.add_argument('--tasks-root', default=str(WORKSPACE_ROOT / 'tasks'))
    return parser


def _format_counts(counts: dict[str, int], *, limit: int = 4) -> str:
    items = list(counts.items())
    if not items:
        return '-'
    rendered = [f'{key}:{value}' for key, value in items[:limit]]
    if len(items) > limit:
        rendered.append(f'+{len(items) - limit} more')
    return ', '.join(rendered)


def _render_group_section(name: str, groups: list[dict[str, object]], *, limit: int) -> list[str]:
    rows = groups[:max(limit, 1)]
    label_width = max([len(name), *(len(str(row.get('label') or '')) for row in rows)] or [len(name)])
    lines = [
        f'[{name}]',
        f"{'label':<{label_width}}  {'tasks':>5}  {'blocked':>7}  {'active':>6}  {'ready':>5}  board_status",
    ]
    for row in rows:
        lines.append(
            f"{str(row.get('label') or ''):<{label_width}}  {int(row.get('task_count') or 0):>5}  {int(row.get('blocked_count') or 0):>7}  {int(row.get('active_count') or 0):>6}  {int(row.get('ready_for_merge_count') or 0):>5}  {_format_counts(dict(row.get('board_status_counts') or {}))}"
        )
    if len(groups) > len(rows):
        lines.append(f'... {len(groups) - len(rows)} more group(s) omitted')
    return lines


def render_text_report(payload: dict[str, object], *, group_limit: int) -> str:
    summary = dict(payload.get('summary') or {})
    filters = dict(payload.get('filters') or {})
    groupings = dict(payload.get('groupings') or {})
    request_trees = list(payload.get('request_trees') or [])
    lines = [
        'Task aggregate view (read-only)',
        f"generated_at: {payload.get('generated_at')}",
        f"last_synced_at: {summary.get('last_synced_at')}",
        'filters: ' + ', '.join(f'{key}={value or "*"}' for key, value in filters.items()),
        (
            f"tasks={int(summary.get('task_count') or 0)} | "
            f"blocked={int(summary.get('blocked_count') or 0)} | "
            f"active={int(summary.get('active_count') or 0)} | "
            f"ready_for_merge={int(summary.get('ready_for_merge_count') or 0)} | "
            f"done={int(summary.get('done_count') or 0)}"
        ),
        'board_status: ' + _format_counts(dict(summary.get('board_status_counts') or {}), limit=8),
        'task_level: ' + _format_counts(dict(summary.get('task_level_counts') or {}), limit=8),
        '',
    ]
    for dimension in ('owner_pm', 'domain', 'task_level', 'parent_task_id', 'root_request_id'):
        lines.extend(_render_group_section(dimension, list(groupings.get(dimension) or []), limit=group_limit))
        lines.append('')

    lines.append('[request_trees]')
    for tree in request_trees[:max(group_limit, 1)]:
        lines.append(
            f"- {tree.get('label')}: tasks={tree.get('task_count')} blocked={tree.get('blocked_count')} active={tree.get('active_count')} ready={tree.get('ready_for_merge_count')} parents={tree.get('parent_group_count')}"
        )
        for parent in list(tree.get('parent_groups') or [])[:3]:
            lines.append(
                f"    * {parent.get('label')}: tasks={parent.get('task_count')} board={_format_counts(dict(parent.get('board_status_counts') or {}), limit=3)}"
            )
    if len(request_trees) > max(group_limit, 1):
        lines.append(f'... {len(request_trees) - max(group_limit, 1)} more root request tree(s) omitted')
    lines.append('')
    lines.append('note: this report is derived from the task read model for inspection only; it does not mutate task facts or replace task.json as source of truth.')
    return '\n'.join(lines)


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    payload: dict[str, object]
    if args.sync_first:
        backfill_tasks(args.tasks_root, db_path=args.db, source='task-aggregate-sync')
    conn = connect_db(args.db, initialize=True)
    try:
        payload = build_task_aggregate_payload(
            conn,
            project=args.project,
            owner_pm=args.owner_pm,
            domain=args.domain,
            task_level=args.task_level,
            parent_task_id=args.parent_task_id,
            root_request_id=args.root_request_id,
        )
    finally:
        conn.close()

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
    else:
        print(render_text_report(payload, group_limit=args.group_limit))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
