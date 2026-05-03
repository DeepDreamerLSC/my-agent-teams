#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import json
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any


def parse_dt(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace('Z', '+00:00')).astimezone()
    except Exception:
        return None


def load_rows(chat_root: Path, cutoff: datetime) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    patterns = [
        chat_root / 'general',
        chat_root / 'tasks',
        chat_root / 'system' / 'watcher',
        chat_root / 'system' / 'dispatch',
        chat_root / 'system' / 'direct_nudge',
    ]
    for base in patterns:
        if not base.exists():
            continue
        for path in sorted(base.rglob('*.jsonl')):
            for idx, line in enumerate(path.read_text(encoding='utf-8').splitlines(), start=1):
                if not line.strip():
                    continue
                try:
                    row = json.loads(line)
                except json.JSONDecodeError:
                    continue
                dt = parse_dt(row.get('ts'))
                if dt is None or dt < cutoff:
                    continue
                row['_dt'] = dt
                row['_file'] = str(path)
                row['_line'] = idx
                rows.append(row)
    rows.sort(key=lambda item: item['_dt'])
    return rows


def summarize(rows: list[dict[str, Any]]) -> dict[str, Any]:
    counters = Counter()
    type_counter = Counter()
    severity_counter = Counter()
    unanswered_questions: list[dict[str, Any]] = []

    answers_by_reply: set[str] = set()
    for row in rows:
        type_counter[row.get('type') or 'unknown'] += 1
        if row.get('severity'):
            severity_counter[row['severity']] += 1
        if row.get('type') == 'answer' and row.get('reply_to'):
            answers_by_reply.add(str(row['reply_to']))

    task_announce_rows = []
    nudge_by_task = Counter()

    for row in rows:
        msg = str(row.get('msg') or '')
        row_type = row.get('type')
        task_id = row.get('task_id')
        source_type = row.get('source_type')
        counters['message_count'] += 1
        if row.get('schema_version') is not None:
            counters['schema_version_present_count'] += 1
        if row_type == 'task_announce':
            counters['task_announce_count'] += 1
            task_announce_rows.append(row)
        if row_type == 'question':
            counters['question_count'] += 1
            if str(row.get('msg_id')) not in answers_by_reply:
                unanswered_questions.append(row)
        if row_type == 'answer':
            counters['answer_count'] += 1
        if row_type == 'decision':
            counters['decision_count'] += 1
        if row_type == 'task_done':
            counters['task_done_count'] += 1
        if '@pm-chief' in msg or row.get('to') == 'pm-chief':
            counters['pm_mention_count'] += 1
        if row.get('priority') == 'critical':
            counters['critical_message_count'] += 1
        if source_type == 'system' and row_type == 'nudge' and task_id:
            nudge_by_task[str(task_id)] += 1
        if source_type == 'system':
            counters['system_event_count'] += 1
        else:
            counters['human_event_count'] += 1

    critical_dual = 0
    for row in task_announce_rows:
        if row.get('priority') == 'critical' and row.get('task_id') and nudge_by_task[str(row['task_id'])] > 0:
            critical_dual += 1
    counters['critical_dual_channel_count'] = critical_dual
    counters['unanswered_question_count'] = len(unanswered_questions)

    ratio = None
    if counters['question_count']:
        ratio = round(counters['answer_count'] / counters['question_count'], 3)

    schema_coverage = None
    if counters['message_count']:
        schema_coverage = round(counters['schema_version_present_count'] / counters['message_count'], 3)

    return {
        'summary': {
            **counters,
            'question_answer_ratio': ratio,
            'schema_version_coverage': schema_coverage,
        },
        'type_counts': dict(type_counter),
        'severity_counts': dict(severity_counter),
        'unanswered_questions': [
            {
                'msg_id': row.get('msg_id'),
                'task_id': row.get('task_id'),
                'from': row.get('from'),
                'ts': row.get('ts'),
                'msg': row.get('msg'),
            }
            for row in unanswered_questions[-20:]
        ],
    }


def main() -> int:
    parser = argparse.ArgumentParser(description='Collect Chat Hub validation metrics.')
    parser.add_argument('--chat-root', default=str(Path.home() / 'Desktop/work/my-agent-teams/chat'))
    parser.add_argument('--days', type=int, default=1)
    parser.add_argument('--json', action='store_true')
    args = parser.parse_args()

    chat_root = Path(args.chat_root).expanduser().resolve()
    cutoff = datetime.now().astimezone() - timedelta(days=max(1, args.days))
    rows = load_rows(chat_root, cutoff)
    payload = summarize(rows)
    payload['chat_root'] = str(chat_root)
    payload['days'] = max(1, args.days)
    payload['generated_at'] = datetime.now().astimezone().isoformat(timespec='seconds')

    if args.json:
        print(json.dumps(payload, ensure_ascii=False, indent=2))
        return 0

    summary = payload['summary']
    print(f"Chat Metrics | days={payload['days']} | root={payload['chat_root']}")
    print(f"- task_announce_count: {summary.get('task_announce_count', 0)}")
    print(f"- question_count: {summary.get('question_count', 0)}")
    print(f"- answer_count: {summary.get('answer_count', 0)}")
    print(f"- question_answer_ratio: {summary.get('question_answer_ratio')}")
    print(f"- pm_mention_count: {summary.get('pm_mention_count', 0)}")
    print(f"- critical_dual_channel_count: {summary.get('critical_dual_channel_count', 0)}")
    print(f"- decision_count: {summary.get('decision_count', 0)}")
    print(f"- task_done_count: {summary.get('task_done_count', 0)}")
    print(f"- unanswered_question_count: {summary.get('unanswered_question_count', 0)}")
    print(f"- schema_version_coverage: {summary.get('schema_version_coverage')}")
    if payload['severity_counts']:
        print(f"- severity_counts: {payload['severity_counts']}")
    if payload['unanswered_questions']:
        print('Unanswered questions:')
        for row in payload['unanswered_questions']:
            print(f"  - [{row.get('ts')}] {row.get('task_id') or '-'} {row.get('msg')}")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
