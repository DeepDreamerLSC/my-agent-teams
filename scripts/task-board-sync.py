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

from dashboard.ingest import backfill_tasks, sync_task_dir  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Sync task metadata into the task-board SQLite database.')
    subparsers = parser.add_subparsers(dest='command', required=True)

    backfill_parser = subparsers.add_parser('backfill', help='Backfill the full tasks/ directory into SQLite.')
    backfill_parser.add_argument('--tasks-root', default=str(WORKSPACE_ROOT / 'tasks'))
    backfill_parser.add_argument('--db', default=None)
    backfill_parser.add_argument('--source', default='backfill')

    sync_parser = subparsers.add_parser('sync-task', help='Sync a single task directory into SQLite.')
    sync_parser.add_argument('--task-dir', required=True)
    sync_parser.add_argument('--db', default=None)
    sync_parser.add_argument('--source', default='watcher')
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == 'backfill':
        payload = backfill_tasks(args.tasks_root, db_path=args.db, source=args.source)
    else:
        payload = sync_task_dir(args.task_dir, db_path=args.db, source=args.source)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
