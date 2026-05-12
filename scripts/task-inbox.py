#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE_ROOT = SCRIPT_DIR.parent
DEFAULT_GOVERNANCE_FILE = WORKSPACE_ROOT / '.omx' / 'task-board' / 'pm-inbox-governance.json'
sys.path.insert(0, str(SCRIPT_DIR / 'lib'))
import task_artifacts  # type: ignore

SEVERITY_RANK = {'L3': 3, 'L2': 2, 'L1': 1}
PRIORITY_RANK = {'critical': 4, 'urgent': 4, 'high': 3, 'medium': 2, 'low': 1}


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


def recommended_action(reason_type: str, gate: str, status: str) -> str:
    if reason_type == 'blocked':
        if gate == 'review_rejected':
            return '查看 review 结论并决定补修/改派/关闭'
        if gate == 'qa_failed':
            return '查看 verify 结论并决定修复/回退/重新验证'
        return '查看 blocked 原因并决定恢复、拆分或取消'
    if reason_type == 'acceptance':
        return '检查产物与验证证据，决定 close-task 或继续补证据'
    if reason_type == 'artifact_invalid':
        return '要求执行者修正机器产物 JSON，修正后 watcher 自动继续'
    if reason_type == 'stale_resume':
        return '使用 resume-task.sh 正规恢复，归档旧工件并清理 sentinel'
    if reason_type == 'timeout':
        if status == 'working':
            return '联系执行者确认进展，必要时转 blocked 或拆补修任务'
        if status == 'dispatched':
            return '确认 agent 是否已看到任务，必要时重新派发或改派'
        if status == 'pooled':
            return '确认是否转派/拆小/提优先级'
        return '检查队列卡点并决定转派或仲裁'
    return '查看任务详情并决定下一步'


def make_item(task_dir: Path, reason_type: str, severity: str, summary: str, now: datetime) -> dict:
    task = task_artifacts.parse_task(task_dir)['task']
    task_id = str(task.get('id') or task_dir.name)
    title = str(task.get('title') or task_id)
    status = str(task.get('status') or '')
    gate = str(task.get('merge_gate_state') or '')
    updated_at = parse_iso(str(task.get('updated_at') or ''))
    resume_round = int(task.get('resume_round') or 0)
    return {
        'item_id': f"{task_id}:{reason_type}:{status or gate}:{resume_round}",
        'task_id': task_id,
        'title': title,
        'reason_type': reason_type,
        'severity': severity,
        'priority': str(task.get('priority') or 'medium'),
        'status': status,
        'merge_gate_state': gate,
        'summary': summary,
        'recommended_action': recommended_action(reason_type, gate, status),
        'owner': str(task.get('owner_pm') or 'pm-chief'),
        'first_seen_at': updated_at.isoformat(timespec='seconds') if updated_at else '',
        'last_seen_at': updated_at.isoformat(timespec='seconds') if updated_at else '',
        'age_minutes': age_minutes(updated_at, now),
        'links': {
            'task_dir': str(task_dir),
            'timeline': str(Path('chat/tasks') / f'{task_id}.jsonl'),
        },
    }


def task_items(task_dir: Path, now: datetime, dispatch_timeout_s: int, working_timeout_s: int) -> list[dict]:
    task_payload = task_artifacts.parse_task(task_dir)['task']
    status = str(task_payload.get('status') or '')
    gate = str(task_payload.get('merge_gate_state') or '')
    items: list[dict] = []

    if status in {'done', 'cancelled', 'archived'}:
        return items

    if status == 'blocked' or gate in {'review_rejected', 'qa_failed', 'blocked'}:
        items.append(make_item(task_dir, 'blocked', 'L3', f'任务处于 {status} / {gate or "无 gate"} 状态，需要 PM 仲裁', now))
        return items

    if gate == 'pm_acceptance_pending':
        items.append(make_item(task_dir, 'acceptance', 'L2', 'review/QA 已满足，等待 PM 最终收口', now))

    result_info = task_artifacts.parse_result(task_dir)
    review_info = task_artifacts.parse_review(task_dir)
    verify_info = task_artifacts.parse_verify(task_dir)
    ack_info = task_artifacts.parse_ack(task_dir)

    for kind, info in [('result', result_info), ('review', review_info), ('verify', verify_info), ('ack', ack_info)]:
        if info.get('valid') is False and info.get('errors'):
            detail = ','.join(info.get('errors') or ['unknown'])
            items.append(make_item(task_dir, 'artifact_invalid', 'L2', f'{kind} 产物非法：{detail}', now))

    if status in {'dispatched', 'working'}:
        if ack_info.get('exists') and not ack_info.get('is_current_round', True):
            items.append(make_item(task_dir, 'stale_resume', 'L2', '恢复后仍存在旧 ack.json，可能干扰新一轮执行', now))
        if result_info.get('exists') and not result_info.get('is_current_round', True):
            items.append(make_item(task_dir, 'stale_resume', 'L2', '恢复后仍存在旧 result.json，可能干扰新一轮执行', now))

    now_epoch = int(now.timestamp())
    dispatch_ref = task_artifacts.iso_to_epoch(task_payload.get('lease_acquired_at') or task_payload.get('updated_at'))
    ack_ref = result_info.get('mtime_epoch') or 0
    if status == 'dispatched' and not ack_info.get('exists') and dispatch_ref and now_epoch - dispatch_ref > dispatch_timeout_s:
        items.append(make_item(task_dir, 'timeout', 'L2', f'dispatched 超过 {dispatch_timeout_s // 60 or 1} 分钟仍无 ack', now))
    if status == 'working':
        working_ref = ack_info.get('mtime_epoch') or task_artifacts.iso_to_epoch(task_payload.get('updated_at'))
        if working_ref and now_epoch - working_ref > working_timeout_s:
            items.append(make_item(task_dir, 'timeout', 'L3', f'working 超过 {working_timeout_s // 60} 分钟仍无新结果', now))
    if status == 'pooled':
        pool_entered_at = parse_iso(str(task_payload.get('pool_entered_at') or ''))
        timeout_minutes = int(task_payload.get('pool_timeout_minutes') or 0)
        if pool_entered_at and timeout_minutes > 0 and age_minutes(pool_entered_at, now) > timeout_minutes:
            items.append(make_item(task_dir, 'timeout', 'L2', f'pooled 超过 {timeout_minutes} 分钟仍未认领', now))
    if status == 'ready_for_merge':
        gate_changed_at = parse_iso(str(task_payload.get('last_gate_decision_at') or task_payload.get('updated_at') or ''))
        gate_wait_minutes = age_minutes(gate_changed_at, now)
        review_deadline = parse_iso(str(task_payload.get('review_deadline') or ''))
        review_timeout_minutes = 120
        qa_timeout_minutes = 120
        if gate == 'review_pending':
            if review_deadline and now > review_deadline:
                items.append(make_item(task_dir, 'timeout', 'L2', 'review_deadline 已过，review_pending 仍未收敛', now))
            elif gate_wait_minutes > review_timeout_minutes:
                items.append(make_item(task_dir, 'timeout', 'L2', f'review_pending 超过 {review_timeout_minutes} 分钟仍未收敛', now))
        if gate == 'qa_pending' and gate_wait_minutes > qa_timeout_minutes:
            items.append(make_item(task_dir, 'timeout', 'L2', f'qa_pending 超过 {qa_timeout_minutes} 分钟仍未收敛', now))

    return items


def sort_key(item: dict) -> tuple:
    return (
        -SEVERITY_RANK.get(item['severity'], 0),
        -PRIORITY_RANK.get(str(item.get('priority') or '').lower(), 0),
        -int(item.get('age_minutes') or 0),
        item['task_id'],
    )


def load_governance_items(path: Path) -> list[dict]:
    if not path.exists():
        return []
    try:
        payload = json.loads(path.read_text(encoding='utf-8'))
    except Exception:
        return []
    return payload if isinstance(payload, list) else []


def print_human(items: list[dict]) -> None:
    by_level = {'L3': 0, 'L2': 0, 'L1': 0}
    for item in items:
        by_level[item['severity']] = by_level.get(item['severity'], 0) + 1
    acceptance = sum(1 for item in items if item['reason_type'] == 'acceptance')
    oldest = max((int(item.get('age_minutes') or 0) for item in items), default=0)
    print(f"PM Inbox | L3 {by_level.get('L3', 0)} | L2 {by_level.get('L2', 0)} | acceptance {acceptance} | oldest {oldest}m")
    print()
    for item in items:
        print(f"[{item['severity']}][{item['reason_type']}][{item['priority']}] {item['title']} age={item['age_minutes']}m")
        print(f"  reason: {item['summary']}")
        print(f"  next: {item['recommended_action']}")
        print()


def main() -> int:
    parser = argparse.ArgumentParser(description='Aggregate PM inbox items from task facts')
    parser.add_argument('--tasks-root', default=str(Path.home() / 'Desktop/work/my-agent-teams/tasks'))
    parser.add_argument('--json', action='store_true')
    parser.add_argument('--reason', default='')
    parser.add_argument('--severity', default='')
    parser.add_argument('--explain', default='')
    parser.add_argument('--dispatch-timeout-seconds', type=int, default=300)
    parser.add_argument('--working-timeout-seconds', type=int, default=1800)
    parser.add_argument('--governance-file', default=str(DEFAULT_GOVERNANCE_FILE))
    args = parser.parse_args()

    tasks_root = Path(args.tasks_root).expanduser().resolve()
    now = datetime.now().astimezone()
    items: list[dict] = []
    for task_path in sorted(tasks_root.glob('*/task.json')):
        items.extend(task_items(task_path.parent, now, args.dispatch_timeout_seconds, args.working_timeout_seconds))
    items.extend(load_governance_items(Path(args.governance_file).expanduser()))

    if args.explain:
        items = [item for item in items if item['task_id'] == args.explain]
    if args.reason:
        allowed = {part.strip() for part in args.reason.split(',') if part.strip()}
        items = [item for item in items if item['reason_type'] in allowed]
    if args.severity:
        allowed = {part.strip() for part in args.severity.split(',') if part.strip()}
        items = [item for item in items if item['severity'] in allowed]

    items.sort(key=sort_key)
    if args.json:
        print(json.dumps(items, ensure_ascii=False, indent=2))
    else:
        print_human(items)
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
