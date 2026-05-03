#!/usr/bin/env python3
# -*- coding: utf-8 -*-
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def infer_channel(path: Path) -> str:
    parts = path.parts
    if 'general' in parts:
        return 'general'
    if 'tasks' in parts:
        return 'task'
    if 'watcher' in parts:
        return 'watcher'
    if 'dispatch' in parts:
        return 'dispatch'
    if 'direct_nudge' in parts:
        return 'direct_nudge'
    return 'unknown'


def infer_event_class(row: dict[str, Any], channel: str) -> str:
    row_type = str(row.get('type') or 'text').strip()
    source_type = str(row.get('source_type') or 'human').strip()
    if source_type == 'system':
        if row_type == 'nudge' or channel == 'direct_nudge':
            return 'delivery'
        return 'system_notice'
    if row_type in {'task_announce', 'task_done'}:
        return 'task_marker'
    return 'message'


def infer_source_name(row: dict[str, Any], channel: str) -> str | None:
    if str(row.get('source_type') or '').strip() != 'system':
        return None
    mapping = {
        'watcher': 'task-watcher',
        'dispatch': 'dispatch-task',
        'direct_nudge': 'send-to-agent',
    }
    return mapping.get(channel)


def normalize_row(row: dict[str, Any], path: Path) -> tuple[dict[str, Any], bool]:
    changed = False
    channel = str(row.get('channel') or '').strip()
    if not channel:
        row['channel'] = infer_channel(path)
        channel = row['channel']
        changed = True
    if 'schema_version' not in row:
        row['schema_version'] = 1
        changed = True
    if 'event_class' not in row or not str(row.get('event_class') or '').strip():
        row['event_class'] = infer_event_class(row, channel)
        changed = True
    if str(row.get('source_type') or '').strip() == 'system':
        if 'severity' not in row or not str(row.get('severity') or '').strip():
            row['severity'] = 'info'
            changed = True
        if 'source_name' not in row or not str(row.get('source_name') or '').strip():
            inferred = infer_source_name(row, channel)
            if inferred:
                row['source_name'] = inferred
                changed = True
    return row, changed


def process_file(path: Path, *, dry_run: bool) -> tuple[int, int]:
    raw_lines = path.read_text(encoding='utf-8').splitlines()
    total = 0
    changed_count = 0
    output_lines: list[str] = []
    for line in raw_lines:
        if not line.strip():
            output_lines.append(line)
            continue
        total += 1
        try:
            row = json.loads(line)
        except json.JSONDecodeError:
            output_lines.append(line)
            continue
        row, changed = normalize_row(row, path)
        if changed:
            changed_count += 1
        output_lines.append(json.dumps(row, ensure_ascii=False))
    if changed_count and not dry_run:
        path.write_text('\n'.join(output_lines) + '\n', encoding='utf-8')
    return total, changed_count


def main() -> int:
    parser = argparse.ArgumentParser(description='Normalize historical chat JSONL records with schema_version/channel defaults.')
    parser.add_argument('--chat-root', default=str(Path.home() / 'Desktop/work/my-agent-teams/chat'))
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    root = Path(args.chat_root).expanduser().resolve()
    files = sorted(root.rglob('*.jsonl'))
    file_count = 0
    changed_files = 0
    total_rows = 0
    changed_rows = 0
    for path in files:
        file_count += 1
        total, changed = process_file(path, dry_run=args.dry_run)
        total_rows += total
        changed_rows += changed
        if changed:
            changed_files += 1
            print(f'normalized {path} ({changed}/{total} rows changed)')
    print(
        json.dumps(
            {
                'chat_root': str(root),
                'file_count': file_count,
                'changed_files': changed_files,
                'total_rows': total_rows,
                'changed_rows': changed_rows,
                'dry_run': args.dry_run,
            },
            ensure_ascii=False,
            indent=2,
        )
    )
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
