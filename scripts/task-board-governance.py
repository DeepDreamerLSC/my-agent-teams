#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sqlite3
from datetime import datetime
from pathlib import Path
from typing import Any


WORKSPACE_ROOT = Path(__file__).resolve().parents[1]
DEFAULT_DB_PATH = WORKSPACE_ROOT / '.omx' / 'task-board' / 'task-board.sqlite3'
DEFAULT_TASKS_ROOT = WORKSPACE_ROOT / 'tasks'
DEFAULT_PM_INBOX_OUTPUT = WORKSPACE_ROOT / '.omx' / 'task-board' / 'pm-inbox-governance.json'
DEFAULT_CONFIG_FILE = WORKSPACE_ROOT / 'config.json'
DEFAULT_POOLED_SLA_MINUTES = 60
SKIP_REVIEW_WAIT_ALERT_SECONDS = 3600
TERMINAL_STATUSES = {'cancelled', 'failed', 'timeout'}

import sys
sys.path.insert(0, str(WORKSPACE_ROOT / 'scripts' / 'lib'))
from agent_config import load_config, root_pm  # type: ignore


def parse_iso(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        dt = datetime.fromisoformat(value.replace('Z', '+00:00'))
        if dt.tzinfo is None:
            return dt.astimezone()
        return dt
    except Exception:
        return None


def age_minutes(from_dt: datetime | None, now: datetime) -> int:
    if not from_dt:
        return 0
    return max(0, int((now - from_dt).total_seconds() // 60))


def load_task_json(path: str | None) -> dict[str, Any]:
    if not path:
        return {}
    task_json_path = Path(path)
    try:
        payload = json.loads(task_json_path.read_text(encoding='utf-8'))
        return payload if isinstance(payload, dict) else {}
    except Exception:
        return {}


def configured_root_pm(config_path: Path = DEFAULT_CONFIG_FILE) -> str:
    return root_pm(load_config(config_path))


def make_item(*, task: sqlite3.Row, reason_type: str, severity: str, summary: str, recommended_action: str, now: datetime, root_pm_id: str | None = None) -> dict[str, Any]:
    task_id = str(task['task_id'])
    current_status_at = parse_iso(str(task['current_status_at'] or ''))
    updated_at = parse_iso(str(task['updated_at'] or ''))
    anchor = current_status_at or updated_at or parse_iso(str(task['created_at'] or ''))
    return {
        'item_id': f"{task_id}:{reason_type}",
        'task_id': task_id,
        'title': str(task['title'] or task_id),
        'reason_type': reason_type,
        'severity': severity,
        'priority': str(task['priority'] or 'medium'),
        'status': str(task['current_status'] or ''),
        'merge_gate_state': str(task['merge_gate_state'] or ''),
        'summary': summary,
        'recommended_action': recommended_action,
        'owner': str(task['owner_pm'] or root_pm_id or configured_root_pm()),
        'first_seen_at': anchor.isoformat(timespec='seconds') if anchor else '',
        'last_seen_at': anchor.isoformat(timespec='seconds') if anchor else '',
        'age_minutes': age_minutes(anchor, now),
        'links': {
            'task_dir': str(task['task_dir'] or ''),
            'timeline': str(Path('chat/tasks') / f'{task_id}.jsonl'),
        },
        'source': 'task-board-governance',
    }


def find_invalid_timeline_items(conn: sqlite3.Connection, now: datetime, root_pm_id: str | None = None) -> list[dict[str, Any]]:
    rows = conn.execute(
        '''
        SELECT t.*, d.result_to_review_seconds
        FROM tasks t
        LEFT JOIN task_stage_durations d ON d.task_id = t.task_id
        ORDER BY t.task_id ASC
        '''
    ).fetchall()
    items: list[dict[str, Any]] = []
    for row in rows:
        issues: list[str] = []
        checkpoints = [
            ('created_at', 'dispatched_at', '创建→派发'),
            ('dispatched_at', 'ack_at', '派发→接单'),
            ('ack_at', 'completed_at', '接单→交付'),
            ('completed_at', 'review_completed_at', '交付→审查'),
            ('review_completed_at', 'verify_completed_at', '审查→验证'),
        ]
        for start_key, end_key, label in checkpoints:
            start = parse_iso(str(row[start_key] or ''))
            end = parse_iso(str(row[end_key] or ''))
            if start and end and end < start:
                issues.append(f'{label}时间倒挂')
        latest_known = None
        for key in ['verify_completed_at', 'review_completed_at', 'completed_at', 'ack_at', 'dispatched_at', 'created_at']:
            candidate = parse_iso(str(row[key] or ''))
            if candidate:
                latest_known = candidate
                break
        current_status_at = parse_iso(str(row['current_status_at'] or ''))
        if latest_known and current_status_at and current_status_at < latest_known:
            issues.append('终态时间早于上一阶段')

        review_level = str(row['review_level'] or '').strip().lower()
        if (not bool(row['review_required']) or review_level == 'skip') and (row['result_to_review_seconds'] or 0) >= SKIP_REVIEW_WAIT_ALERT_SECONDS:
            issues.append('skip review 却存在长等待审查时长')

        if issues:
            items.append(make_item(
                task=row,
                reason_type='invalid_timeline',
                severity='L2',
                summary='；'.join(issues),
                recommended_action='核对阶段时间线并修正 task.json / 同步数据，避免甘特图误导',
                now=now,
                root_pm_id=root_pm_id,
            ))
    return items


def find_stale_pooled_items(conn: sqlite3.Connection, now: datetime, root_pm_id: str | None = None) -> list[dict[str, Any]]:
    rows = conn.execute("SELECT * FROM tasks WHERE current_status = 'pooled' ORDER BY task_id ASC").fetchall()
    items: list[dict[str, Any]] = []
    for row in rows:
        metadata = load_task_json(row['task_json_path'])
        pool_entered_at = parse_iso(str(metadata.get('pool_entered_at') or row['current_status_at'] or row['updated_at'] or ''))
        timeout_minutes = int(metadata.get('pool_timeout_minutes') or DEFAULT_POOLED_SLA_MINUTES)
        if not pool_entered_at:
            continue
        age = age_minutes(pool_entered_at, now)
        if age <= timeout_minutes:
            continue
        items.append(make_item(
            task=row,
            reason_type='stale_pooled',
            severity='L2',
            summary=f'pooled 等待 {age} 分钟，超过 SLA {timeout_minutes} 分钟',
            recommended_action='请 PM 判断转派、拆小任务或调整优先级',
            now=now,
            root_pm_id=root_pm_id,
        ))
    return items


def find_synthetic_backfill_items(conn: sqlite3.Connection, now: datetime, root_pm_id: str | None = None) -> list[dict[str, Any]]:
    rows = conn.execute(
        '''
        SELECT *
        FROM tasks
        WHERE current_status IN ('cancelled', 'failed', 'timeout')
        ORDER BY task_id ASC
        '''
    ).fetchall()
    items: list[dict[str, Any]] = []
    for row in rows:
        if not row['current_status_at']:
            summary = '终态任务缺少 current_status_at，甘特图只能依赖合成结束点'
        elif not any(row[key] for key in ('completed_at', 'review_completed_at', 'verify_completed_at')):
            summary = '终态任务在交付前结束，需确认 current_status_at 作为真实收口时间'
        else:
            continue
        items.append(make_item(
            task=row,
            reason_type='synthetic_backfill',
            severity='L1',
            summary=summary,
            recommended_action='回填或确认终态时间锚点，避免历史任务横轴被错误拉长',
            now=now,
            root_pm_id=root_pm_id,
        ))
    return items


def sort_key(item: dict[str, Any]) -> tuple[int, int, int, str]:
    severity_rank = {'L3': 3, 'L2': 2, 'L1': 1}
    priority_rank = {'critical': 4, 'urgent': 4, 'high': 3, 'medium': 2, 'low': 1}
    return (
        -severity_rank.get(item['severity'], 0),
        -priority_rank.get(str(item.get('priority') or '').lower(), 0),
        -int(item.get('age_minutes') or 0),
        item['task_id'],
    )


def write_pm_inbox(items: list[dict[str, Any]], output_path: Path) -> None:
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(items, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def main() -> int:
    parser = argparse.ArgumentParser(description='Task board data governance checks')
    parser.add_argument('--db-path', default=str(DEFAULT_DB_PATH))
    parser.add_argument('--pm-inbox-output', default=str(DEFAULT_PM_INBOX_OUTPUT))
    parser.add_argument('--config', default=str(DEFAULT_CONFIG_FILE))
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()

    conn = sqlite3.connect(Path(args.db_path).expanduser())
    conn.row_factory = sqlite3.Row
    now = datetime.now().astimezone()
    root_pm_id = configured_root_pm(Path(args.config).expanduser())
    items = [
        *find_invalid_timeline_items(conn, now, root_pm_id=root_pm_id),
        *find_stale_pooled_items(conn, now, root_pm_id=root_pm_id),
        *find_synthetic_backfill_items(conn, now, root_pm_id=root_pm_id),
    ]
    items.sort(key=sort_key)
    write_pm_inbox(items, Path(args.pm_inbox_output).expanduser())
    if args.json:
        print(json.dumps(items, ensure_ascii=False, indent=2))
    else:
        print(f'governance_items={len(items)}')
        for item in items:
            print(f"[{item['severity']}][{item['reason_type']}] {item['task_id']} {item['summary']}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
