#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
sys.path.insert(0, str(SCRIPT_DIR / 'lib'))
import task_artifacts  # type: ignore


def boolish(value) -> bool:
    return str(value).strip().lower() in {'1', 'true', 'yes', 'y'}


def now_iso() -> str:
    return datetime.now().astimezone().isoformat(timespec='seconds')


def attention_item(task_id: str, reason_type: str, summary: str, severity: str = 'L2') -> dict:
    return {
        'task_id': task_id,
        'reason_type': reason_type,
        'severity': severity,
        'summary': summary,
    }


def _review_gate_state_from_artifact(review: dict) -> str:
    normalized = str(review.get('normalized_status') or '').strip().lower()
    if normalized == 'approve':
        return 'approved'
    if normalized == 'request_changes':
        return 'rejected'
    if normalized == 'blocked':
        return 'blocked'
    return 'pending'


def _qa_gate_state_from_artifact(verify: dict) -> str:
    normalized = str(verify.get('normalized_status') or '').strip().lower()
    if normalized == 'pass':
        return 'passed'
    if normalized == 'fail':
        return 'failed'
    if normalized == 'blocked':
        return 'blocked'
    return 'pending'


def reduce_task_state(task_dir: Path) -> dict:
    task_info = task_artifacts.parse_task(task_dir)
    task = task_info['task']
    task_id = str(task.get('id') or task_dir.name)
    status = str(task.get('status') or 'pending').strip() or 'pending'
    gate = task.get('merge_gate_state')
    review_required = boolish(task.get('review_required'))
    test_required = boolish(task.get('test_required'))
    quality_gate_mode = str(task.get('quality_gate_mode') or '').strip().lower()
    task_level = str(task.get('task_level') or '').strip().lower()
    assigned_agent = str(task.get('assigned_agent') or '').strip()

    ack = task_artifacts.parse_ack(task_dir)
    result = task_artifacts.parse_result(task_dir)
    review = task_artifacts.parse_review(task_dir)
    verify = task_artifacts.parse_verify(task_dir)

    patches: dict[str, object] = {}
    actions: list[dict] = []
    attention_items: list[dict] = []
    reason = 'no_change'

    for kind, parsed in [('ack', ack), ('result', result), ('review', review), ('verify', verify)]:
        if parsed.get('normalized_status') == 'invalid':
            attention_items.append(attention_item(task_id, 'artifact_invalid', f'{kind} 产物非法：{(parsed.get("errors") or ["unknown"])[0]}', 'L2'))
    if status in {'done', 'cancelled', 'archived', 'failed', 'timeout'}:
        return {
            'task_id': task_id,
            'current': {'status': status, 'merge_gate_state': gate},
            'artifacts': {
                'ack': ack,
                'result': result,
                'review': review,
                'verify': verify,
            },
            'patches': {},
            'actions': [],
            'attention_items': attention_items,
            'reason': 'terminal_status',
        }
    if status in {'dispatched', 'working'}:
        if ack.get('exists') and not ack.get('is_current_round', True):
            attention_items.append(attention_item(task_id, 'stale_resume', '恢复后检测到旧 ack.json，需重新 ack', 'L2'))
        if result.get('exists') and not result.get('is_current_round', True):
            attention_items.append(attention_item(task_id, 'stale_resume', '恢复后检测到旧 result.json，需忽略旧轮次产物', 'L2'))

    if status == 'dispatched' and ack.get('normalized_status') == 'acknowledged' and ack.get('is_current_round', True):
        patches['status'] = 'working'
        reason = 'ack_current_round'
    elif status in {'dispatched', 'working'} and result.get('normalized_status') == 'success' and result.get('is_current_round', True):
        patches['status'] = 'ready_for_merge'
        patches['rework_reason'] = None
        if review_required and test_required and quality_gate_mode == 'parallel':
            patches['merge_gate_state'] = 'quality_pending'
            patches['review_gate_state'] = 'pending'
            patches['qa_gate_state'] = 'pending'
            actions.append({'type': 'dispatch_review', 'to': task.get('reviewer') or 'review-1'})
            actions.append({'type': 'dispatch_qa', 'to': 'qa-1'})
            reason = 'result.success + quality_pending'
        elif review_required:
            patches['merge_gate_state'] = 'review_pending'
            patches['review_gate_state'] = 'pending'
            patches['qa_gate_state'] = 'pending' if test_required else 'skipped'
            actions.append({'type': 'dispatch_review', 'to': task.get('reviewer') or 'review-1'})
            reason = 'result.success + review_required'
        elif test_required:
            patches['merge_gate_state'] = 'qa_pending'
            patches['review_gate_state'] = 'skipped'
            patches['qa_gate_state'] = 'pending'
            actions.append({'type': 'dispatch_qa', 'to': 'qa-1'})
            reason = 'result.success + qa_required'
        else:
            patches['merge_gate_state'] = 'pm_acceptance_pending'
            patches['review_gate_state'] = 'skipped'
            patches['qa_gate_state'] = 'skipped'
            actions.append({'type': 'notify_pm_acceptance', 'to': task.get('owner_pm') or 'pm-chief'})
            reason = 'result.success + pm_acceptance'
        if assigned_agent:
            actions.append({'type': 'maybe_push_next_execution', 'to': assigned_agent})
    elif result.get('normalized_status') == 'blocked' and result.get('is_current_round', True):
        patches['status'] = 'blocked'
        patches['merge_gate_state'] = 'blocked'
        patches['rework_reason'] = 'execution'
        reason = 'result.blocked'
        attention_items.append(attention_item(task_id, 'blocked', '执行阶段返回 blocked，需要 PM 仲裁', 'L3'))
    elif result.get('normalized_status') == 'failed' and result.get('is_current_round', True):
        patches['status'] = 'blocked'
        patches['merge_gate_state'] = 'blocked'
        patches['rework_reason'] = 'execution'
        reason = 'result.failed'
        attention_items.append(attention_item(task_id, 'blocked', '执行阶段失败，需要 PM 判断补修或关闭', 'L3'))
    elif status == 'ready_for_merge':
        review_state = review.get('normalized_status')
        verify_state = verify.get('normalized_status')
        review_gate_state = 'skipped' if not review_required else _review_gate_state_from_artifact(review)
        qa_gate_state = 'skipped' if not test_required else _qa_gate_state_from_artifact(verify)

        patches['review_gate_state'] = review_gate_state
        patches['qa_gate_state'] = qa_gate_state

        if review_gate_state == 'rejected':
            patches['status'] = 'blocked'
            patches['merge_gate_state'] = 'review_rejected'
            patches['review_gate_state'] = 'rejected'
            patches['rework_reason'] = 'review'
            reason = 'review.request_changes'
            attention_items.append(attention_item(task_id, 'blocked', '审查驳回，需要 PM 仲裁', 'L3'))
        elif review_gate_state == 'blocked':
            patches['status'] = 'blocked'
            patches['merge_gate_state'] = 'blocked'
            patches['review_gate_state'] = 'blocked'
            patches['rework_reason'] = 'review'
            reason = 'review.blocked'
            attention_items.append(attention_item(task_id, 'blocked', '审查阻塞，需要 PM/arch 仲裁', 'L3'))
        elif qa_gate_state in {'failed', 'blocked'}:
            patches['status'] = 'blocked'
            patches['merge_gate_state'] = 'qa_failed'
            patches['qa_gate_state'] = qa_gate_state
            patches['rework_reason'] = 'qa'
            reason = 'verify.fail'
            attention_items.append(attention_item(task_id, 'blocked', 'QA 未通过，需要 PM 仲裁', 'L3'))
        elif review_required and test_required and quality_gate_mode == 'parallel':
            if review_gate_state == 'approved' and qa_gate_state == 'passed':
                patches['merge_gate_state'] = 'pm_acceptance_pending'
                actions.append({'type': 'notify_pm_acceptance', 'to': task.get('owner_pm') or 'pm-chief'})
                reason = 'quality_gates_complete'
            else:
                patches['merge_gate_state'] = 'quality_pending'
                if review_gate_state == 'pending':
                    actions.append({'type': 'dispatch_review', 'to': task.get('reviewer') or 'review-1'})
                if qa_gate_state == 'pending':
                    actions.append({'type': 'dispatch_qa', 'to': 'qa-1'})
                reason = 'quality_pending'
        elif review_required and test_required:
            if review_gate_state == 'approved' and qa_gate_state == 'passed':
                patches['merge_gate_state'] = 'pm_acceptance_pending'
                actions.append({'type': 'notify_pm_acceptance', 'to': task.get('owner_pm') or 'pm-chief'})
                reason = 'serial_quality_gates_complete'
            elif review_gate_state == 'approved':
                patches['merge_gate_state'] = 'qa_pending'
                patches['qa_gate_state'] = 'pending'
                actions.append({'type': 'dispatch_qa', 'to': 'qa-1'})
                reason = 'serial_qa_pending'
            else:
                patches['merge_gate_state'] = 'review_pending'
                actions.append({'type': 'dispatch_review', 'to': task.get('reviewer') or 'review-1'})
                reason = 'review_pending'
        elif not test_required and review_gate_state == 'approved':
            patches['merge_gate_state'] = 'pm_acceptance_pending'
            actions.append({'type': 'notify_pm_acceptance', 'to': task.get('owner_pm') or 'pm-chief'})
            reason = 'review_only_complete'
        elif review_required and review_gate_state == 'pending':
            patches['merge_gate_state'] = 'review_pending'
            actions.append({'type': 'dispatch_review', 'to': task.get('reviewer') or 'review-1'})
            reason = 'review_pending'
        elif review_required and not test_required and review_state == 'approve':
            patches['merge_gate_state'] = 'pm_acceptance_pending'
            patches['review_gate_state'] = 'approved'
            patches['qa_gate_state'] = 'skipped'
            actions.append({'type': 'notify_pm_acceptance', 'to': task.get('owner_pm') or 'pm-chief'})
            reason = 'review_only_complete'
        elif test_required and not review_required:
            if qa_gate_state == 'passed':
                patches['merge_gate_state'] = 'pm_acceptance_pending'
                patches['review_gate_state'] = 'skipped'
                actions.append({'type': 'notify_pm_acceptance', 'to': task.get('owner_pm') or 'pm-chief'})
                reason = 'qa_only_complete'
            else:
                patches['merge_gate_state'] = 'qa_pending'
                patches['review_gate_state'] = 'skipped'
                patches['qa_gate_state'] = 'pending'
                actions.append({'type': 'dispatch_qa', 'to': 'qa-1'})
                reason = 'qa_pending'

    return {
        'task_id': task_id,
        'current': {'status': status, 'merge_gate_state': gate},
        'artifacts': {
            'ack': ack,
            'result': result,
            'review': review,
            'verify': verify,
        },
        'patches': patches,
        'actions': actions,
        'attention_items': attention_items,
        'reason': reason,
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='Pure task state reducer over task facts')
    parser.add_argument('--task-dir', required=True)
    args = parser.parse_args()
    payload = reduce_task_state(Path(args.task_dir).expanduser().resolve())
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
