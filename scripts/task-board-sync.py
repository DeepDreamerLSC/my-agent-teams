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

from dashboard.ingest import backfill_chat, backfill_tasks, sync_chat_file, sync_task_dir  # noqa: E402


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Sync task metadata into the task-board SQLite database.')
    subparsers = parser.add_subparsers(dest='command', required=True)

    backfill_parser = subparsers.add_parser('backfill', help='Backfill the full tasks/ directory into SQLite.')
    backfill_parser.add_argument('--tasks-root', default=str(WORKSPACE_ROOT / 'tasks'))
    backfill_parser.add_argument('--db', default=None)
    backfill_parser.add_argument('--source', default='backfill')
    backfill_parser.add_argument('--chat-root', default=str(WORKSPACE_ROOT / 'chat'))
    backfill_parser.add_argument('--include-chat', action='store_true')
    backfill_parser.add_argument('--full-chat', action='store_true', help='For chat backfill, ignore incremental state and reprocess all lines.')

    sync_parser = subparsers.add_parser('sync-task', help='Sync a single task directory into SQLite.')
    sync_parser.add_argument('--task-dir', required=True)
    sync_parser.add_argument('--db', default=None)
    sync_parser.add_argument('--source', default='watcher')

    chat_backfill_parser = subparsers.add_parser('backfill-chat', help='Backfill chat JSONL files into SQLite communication_events.')
    chat_backfill_parser.add_argument('--chat-root', default=str(WORKSPACE_ROOT / 'chat'))
    chat_backfill_parser.add_argument('--db', default=None)
    chat_backfill_parser.add_argument('--source', default='chat-backfill')
    chat_backfill_parser.add_argument('--full', action='store_true', help='Ignore incremental state and reprocess all lines.')

    sync_chat_parser = subparsers.add_parser('sync-chat', help='Sync a single chat JSONL file into SQLite communication_events.')
    sync_chat_parser.add_argument('--chat-file', required=True)
    sync_chat_parser.add_argument('--db', default=None)
    sync_chat_parser.add_argument('--source', default='chat-sync')
    sync_chat_parser.add_argument('--full', action='store_true', help='Ignore incremental state and reprocess all lines.')
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    if args.command == 'backfill':
        payload = backfill_tasks(args.tasks_root, db_path=args.db, source=args.source)
        if args.include_chat:
            payload['chat'] = backfill_chat(
                args.chat_root,
                db_path=args.db,
                source=f'{args.source}-chat',
                incremental=not args.full_chat,
            )
    elif args.command == 'backfill-chat':
        payload = backfill_chat(args.chat_root, db_path=args.db, source=args.source, incremental=not args.full)
    elif args.command == 'sync-chat':
        payload = sync_chat_file(args.chat_file, db_path=args.db, source=args.source, incremental=not args.full)
    else:
        payload = sync_task_dir(args.task_dir, db_path=args.db, source=args.source)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
