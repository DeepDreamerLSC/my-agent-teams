#!/bin/bash
set -euo pipefail
TASK_FILE="${1:-}"
CONFIG_PATH="${CONFIG_PATH:-$HOME/Desktop/work/my-agent-teams/config.json}"
if [ -z "$TASK_FILE" ]; then
  echo "usage: dispatch-task.sh <task.json>" >&2
  exit 2
fi
python3 - "$TASK_FILE" "$CONFIG_PATH" <<'PY'
import json
import sys
from datetime import datetime
from pathlib import Path

task_path = Path(sys.argv[1]).resolve()
config_path = Path(sys.argv[2]).resolve()
task = json.loads(task_path.read_text(encoding='utf-8'))
config = json.loads(config_path.read_text(encoding='utf-8'))

if task.get('status') != 'pending':
    raise SystemExit(f"task status is {task.get('status')}, expected pending")

project = task.get('project')
projects = config.get('projects', {})
if project not in projects:
    raise SystemExit(f'unknown project: {project}')

agents = config.get('agents', {})
assigned_agent = task.get('assigned_agent')
if assigned_agent not in agents:
    raise SystemExit(f'unknown assigned_agent: {assigned_agent}')

execution_mode = task.get('execution_mode')
target_environment = task.get('target_environment')
if execution_mode not in {'dev', 'deploy'}:
    raise SystemExit('execution_mode invalid')
if target_environment not in {'dev', 'prod'}:
    raise SystemExit('target_environment invalid')
if execution_mode == 'dev' and target_environment != 'dev':
    raise SystemExit('execution_mode=dev requires target_environment=dev')
if execution_mode == 'deploy' and assigned_agent != 'pm-chief':
    raise SystemExit('deploy tasks can only be assigned to pm-chief in Phase 1')
if target_environment == 'prod' and assigned_agent != 'pm-chief':
    raise SystemExit('prod tasks can only be assigned to pm-chief in Phase 1')

project_cfg = projects[project]
dev_root = Path(project_cfg['dev_root']).expanduser().resolve()
prod_root_raw = project_cfg.get('prod_root')
prod_root = Path(prod_root_raw).expanduser().resolve() if prod_root_raw else None

for raw_path in task.get('write_scope') or []:
    p = Path(raw_path).expanduser()
    resolved = p.resolve() if p.is_absolute() else ((prod_root if target_environment == 'prod' and prod_root is not None else dev_root) / p).resolve()
    if prod_root is not None and str(resolved).startswith(str(prod_root)):
        if assigned_agent != 'pm-chief':
            raise SystemExit(f'prod write_scope requires pm-chief: {raw_path}')
    elif not str(resolved).startswith(str(dev_root)):
        raise SystemExit(f'write_scope outside project dev_root: {raw_path}')

now = datetime.now().astimezone().isoformat(timespec='seconds')
previous = task['status']
task['status'] = 'dispatched'
task['updated_at'] = now
task['lease_owner'] = task.get('owner_pm')
task['lease_acquired_at'] = now
task['lease_expires_at'] = now
(task_path.parent / 'transitions.jsonl').open('a', encoding='utf-8').write(json.dumps({
    'from': previous,
    'to': 'dispatched',
    'at': now,
    'reason': 'pm dispatch'
}, ensure_ascii=False) + '\n')
task_path.write_text(json.dumps(task, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
print(f"dispatched {task.get('id')}")
PY
