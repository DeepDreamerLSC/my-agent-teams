#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE_ROOT = SCRIPT_DIR.parent
DEFAULT_GOVERNANCE_FILE = WORKSPACE_ROOT / '.omx' / 'task-board' / 'pm-inbox-governance.json'
DEFAULT_CONFIG_FILE = WORKSPACE_ROOT / 'config.json'
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
    if reason_type == 'pool_starvation':
        return '补齐成熟 pending 任务或处理依赖阻塞，优先恢复可认领池水位'
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
    if reason_type == 'delivery_failed':
        return '检查 send-to-agent 与会话输出，必要时等待阈值后自动转派或人工介入'
    if reason_type == 'session_unhealthy':
        return '优先恢复目标 agent 会话；若连续失败已达阈值，确认自动转派/回池是否合理'
    if reason_type == 'workspace_error':
        return '检查 worktree/workspace 准备异常，必要时修复 repo 状态或临时回退主工作区'
    if reason_type == 'auto_requeue':
        return '确认任务已回到 pooled，并决定是否补定义、调整 scope 或改派'
    if reason_type == 'reassigned':
        return '确认新执行者已收到任务并跟进 ack，必要时补充上下文'
    if reason_type == 'state_invariant_violation':
        return '检查 state_invariant_violations 并修正任务元数据或触发正规恢复流程'
    return '查看任务详情并决定下一步'


def make_global_item(reason_type: str, severity: str, summary: str, now: datetime, *, priority: str = 'medium', links: dict | None = None, age_minutes_value: int = 0) -> dict:
    first_seen = now.isoformat(timespec='seconds')
    return {
        'item_id': f'__global__:{reason_type}',
        'task_id': '__global__',
        'title': '任务池调度健康',
        'reason_type': reason_type,
        'severity': severity,
        'priority': priority,
        'status': '',
        'merge_gate_state': '',
        'summary': summary,
        'recommended_action': recommended_action(reason_type, '', ''),
        'owner': 'pm-chief',
        'first_seen_at': first_seen,
        'last_seen_at': first_seen,
        'age_minutes': age_minutes_value,
        'links': links or {},
    }


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

    result_info = task_artifacts.parse_result(task_dir)
    review_info = task_artifacts.parse_review(task_dir)
    verify_info = task_artifacts.parse_verify(task_dir)
    ack_info = task_artifacts.parse_ack(task_dir)

    if status == 'blocked' or gate in {'review_rejected', 'qa_failed', 'blocked'}:
        if not (status == 'ready_for_merge' and gate == 'review_rejected' and result_info.get('normalized_status') == 'success' and review_info.get('source') == 'stale_json'):
            items.append(make_item(task_dir, 'blocked', 'L3', f'任务处于 {status} / {gate or "无 gate"} 状态，需要 PM 仲裁', now))
            return items

    control_state = str(task_payload.get('control_plane_state') or '').strip().lower()
    last_delivery_error = str(task_payload.get('last_delivery_error') or '').strip()
    workspace_status = str(task_payload.get('workspace_status') or '').strip().lower()
    workspace_error = str(task_payload.get('workspace_error') or '').strip()
    if control_state == 'delivery_failed':
        detail = last_delivery_error or 'send-to-agent 未确认送达'
        items.append(make_item(task_dir, 'delivery_failed', 'L2', f'控制面投递失败：{detail}', now))
    elif control_state == 'session_unhealthy':
        detail = last_delivery_error or '目标 agent 会话不健康或缺失'
        items.append(make_item(task_dir, 'session_unhealthy', 'L2', f'控制面会话异常：{detail}', now))
    if workspace_status == 'error':
        detail = workspace_error or 'worktree/workspace 准备失败'
        items.append(make_item(task_dir, 'workspace_error', 'L2', f'独立工作区异常：{detail}', now))
    if control_state == 'auto_requeue':
        detail = str(task_payload.get('last_auto_requeue_reason') or last_delivery_error or '控制面恢复失败后自动回池').strip()
        items.append(make_item(task_dir, 'auto_requeue', 'L2', f'任务已自动回收到 pooled：{detail}', now))
    elif control_state == 'reassigned':
        detail = str(task_payload.get('last_reassigned_reason') or '连接/会话恢复触发转派').strip()
        items.append(make_item(task_dir, 'reassigned', 'L2', f'任务已自动转派：{detail}', now))

    invariant_violations = task_payload.get('state_invariant_violations')
    if isinstance(invariant_violations, list) and invariant_violations:
        messages = [str(item.get('message') or '') for item in invariant_violations if isinstance(item, dict)]
        summary = '；'.join([item for item in messages if item][:2]) or '任务状态一致性异常，请检查 state_invariant_violations'
        items.append(make_item(task_dir, 'state_invariant_violation', 'L3', summary, now))

    if gate == 'pm_acceptance_pending':
        items.append(make_item(task_dir, 'acceptance', 'L2', 'review/QA 已满足，等待 PM 最终收口', now))

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
        has_artifact_invalid = any(item['reason_type'] == 'artifact_invalid' for item in items)
        if gate == 'review_pending' and not has_artifact_invalid:
            if review_deadline and now > review_deadline:
                items.append(make_item(task_dir, 'timeout', 'L2', 'review_deadline 已过，review_pending 仍未收敛', now))
            elif gate_wait_minutes > review_timeout_minutes:
                items.append(make_item(task_dir, 'timeout', 'L2', f'review_pending 超过 {review_timeout_minutes} 分钟仍未收敛', now))
        if gate == 'qa_pending' and not has_artifact_invalid and gate_wait_minutes > qa_timeout_minutes:
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


def _load_pool_view_module():
    spec = importlib.util.spec_from_file_location('task_pool_view', SCRIPT_DIR / 'task-pool-view.py')
    module = importlib.util.module_from_spec(spec)
    assert spec.loader is not None
    spec.loader.exec_module(module)
    return module


def pool_starvation_items(tasks_root: Path, config_path: Path, now: datetime) -> list[dict]:
    try:
        pool_view = _load_pool_view_module()
        config = pool_view.load_json(config_path)
        agents = config.get('agents') or {}
        default_concurrency = int((config.get('task_pool') or {}).get('default_claim_max_concurrency', 1))
        wip_limits = config.get('wip_limits') or {}
        active_by_agent = pool_view.active_tasks_by_agent(tasks_root)
        rows = []
        for task_dir, task in pool_view.pooled_tasks(tasks_root):
            task['__wip_limits__'] = wip_limits
            rows.append(pool_view.build_row(task_dir, task, agents, active_by_agent, tasks_root, default_concurrency, now, config))
        summary = pool_view.build_summary(rows, agents, active_by_agent, tasks_root)
    except Exception:
        return []

    has_actionable_backlog = bool(
        summary.get('pool_waiting_dependency_count')
        or summary.get('mature_pending_count')
        or summary.get('pooled_count')
    )
    if int(summary.get('idle_agent_count') or 0) <= 0:
        return []
    if int(summary.get('pool_ready_count') or 0) > 0:
        return []
    if not has_actionable_backlog:
        return []

    idle_agents = ','.join(summary.get('idle_agents') or [])
    text = (
        f"空闲 agent {summary.get('idle_agent_count')} 个（{idle_agents or '未列出'}），"
        f"当前可认领任务为 0；依赖等待 {summary.get('pool_waiting_dependency_count', 0)}，"
        f"成熟 pending {summary.get('mature_pending_count', 0)}。"
    )
    return [make_global_item(
        'pool_starvation',
        'L2',
        text,
        now,
        priority='high',
        age_minutes_value=int(summary.get('oldest_pool_wait_minutes') or 0),
        links={'tasks_root': str(tasks_root), 'config': str(config_path)},
    )]


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
    parser.add_argument('--control-config', default='')
    args = parser.parse_args()
    if args.control_config:
        import os
        os.environ['TASK_CONTROL_CONFIG_PATH'] = str(Path(args.control_config).expanduser().resolve())

    tasks_root = Path(args.tasks_root).expanduser().resolve()
    now = datetime.now().astimezone()
    items: list[dict] = []
    for task_path in sorted(tasks_root.glob('*/task.json')):
        items.extend(task_items(task_path.parent, now, args.dispatch_timeout_seconds, args.working_timeout_seconds))
    config_path = Path(args.control_config).expanduser().resolve() if args.control_config else DEFAULT_CONFIG_FILE
    items.extend(pool_starvation_items(tasks_root, config_path, now))
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
