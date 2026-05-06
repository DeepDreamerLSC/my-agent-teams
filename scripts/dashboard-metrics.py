#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import sys
from datetime import date
from pathlib import Path

SCRIPT_DIR = Path(__file__).resolve().parent
WORKSPACE_ROOT = SCRIPT_DIR.parent
if str(WORKSPACE_ROOT) not in sys.path:
    sys.path.insert(0, str(WORKSPACE_ROOT))

from dashboard.ingest import backfill_tasks
from dashboard.metrics import rebuild_daily_metrics


def _parse_date(value: str | None) -> date | None:
    if not value:
        return None
    return date.fromisoformat(value)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description='Rebuild dashboard daily metrics from SQLite task facts.')
    parser.add_argument('--db', default=None)
    parser.add_argument('--project', default=None)
    parser.add_argument('--start-date', default=None, help='YYYY-MM-DD')
    parser.add_argument('--end-date', default=None, help='YYYY-MM-DD')
    parser.add_argument('--sync-first', action='store_true', help='Backfill tasks/ before rebuilding metrics')
    parser.add_argument('--tasks-root', default=str(WORKSPACE_ROOT / 'tasks'))
    return parser


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()
    payload: dict[str, object] = {}
    if args.sync_first:
        payload['sync'] = backfill_tasks(args.tasks_root, db_path=args.db, source='dashboard-metrics-sync')
    payload['metrics'] = rebuild_daily_metrics(
        args.db,
        start_date=_parse_date(args.start_date),
        end_date=_parse_date(args.end_date),
        project=args.project,
    )
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
