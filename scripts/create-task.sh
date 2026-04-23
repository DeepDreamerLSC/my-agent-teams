#!/bin/bash
set -euo pipefail

WORKSPACE_ROOT="${WORKSPACE_ROOT:-$HOME/Desktop/work/my-agent-teams}"
TASKS_DIR="$WORKSPACE_ROOT/tasks"
TASK_ID="${1:-}"
TITLE="${2:-}"
ASSIGNED_AGENT="${3:-}"
DOMAIN="${4:-}"
WRITE_SCOPE_CSV="${5:-}"
REVIEW_REQUIRED="${6:-false}"
TEST_REQUIRED="${7:-false}"
CONFIG_PATH="${CONFIG_PATH:-$WORKSPACE_ROOT/config.json}"

if [ -z "$TASK_ID" ] || [ -z "$TITLE" ] || [ -z "$ASSIGNED_AGENT" ] || [ -z "$DOMAIN" ]; then
  echo "usage: create-task.sh <task-id> <title> <assigned-agent> <domain> [write-scope-csv] [review-required] [test-required]" >&2
  exit 2
fi

TASK_DIR="$TASKS_DIR/$TASK_ID"
mkdir -p "$TASK_DIR"

python3 - "$CONFIG_PATH" "$TASK_ID" "$TITLE" "$ASSIGNED_AGENT" "$DOMAIN" "$WRITE_SCOPE_CSV" "$REVIEW_REQUIRED" "$TEST_REQUIRED" "$TASK_DIR" <<'PY'
import json
import sys
from datetime import datetime
from pathlib import Path

cfg_path = Path(sys.argv[1])
task_id, title, assigned_agent, domain, write_scope_csv, review_required_raw, test_required_raw, task_dir = sys.argv[2:10]
cfg = json.loads(cfg_path.read_text(encoding='utf-8'))
review_required = review_required_raw.lower() == 'true'
test_required = test_required_raw.lower() == 'true'
write_scope = [item.strip() for item in write_scope_csv.split(',') if item.strip()] if write_scope_csv else []
reviewer = cfg.get('domain_policies', {}).get(domain, {}).get('default_reviewer') if review_required else None
created_at = datetime.now().astimezone().isoformat(timespec='seconds')
obj = {
    'id': task_id,
    'title': title,
    'assigned_agent': assigned_agent,
    'review_required': review_required,
    'reviewer': reviewer,
    'test_required': test_required,
    'status': 'pending',
    'task_level': cfg.get('defaults', {}).get('task_level', 'execution'),
    'owner_pm': cfg.get('orchestration', {}).get('root_pm', 'pm-chief'),
    'domain': domain,
    'write_scope': write_scope,
    'depends_on': [],
    'blocks': [],
    'artifacts': [
        {
            'type': 'instruction',
            'path': f'tasks/{task_id}/instruction.md',
            'description': 'PM 生成的任务指令'
        }
    ],
    'root_request_id': task_id,
    'parent_task_id': None,
    'integration_owner': cfg.get('orchestration', {}).get('integration_owner'),
    'priority': 'medium',
    'timeout_minutes': cfg.get('defaults', {}).get('timeout_minutes', 30),
    'lease_owner': cfg.get('orchestration', {}).get('root_pm', 'pm-chief'),
    'lease_acquired_at': created_at,
    'lease_expires_at': created_at,
    'workspace_mode': cfg.get('defaults', {}).get('workspace_mode', 'main'),
    'target_branch': cfg.get('defaults', {}).get('target_branch', 'integration'),
    'result_summary': None,
    'last_error': None,
    'created_at': created_at,
    'updated_at': created_at
}
Path(task_dir, 'task.json').write_text(json.dumps(obj, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
Path(task_dir, 'instruction.md').write_text(f'# 任务：{title}\n\n## 目标\n（待 PM 填写）\n', encoding='utf-8')
Path(task_dir, 'transitions.jsonl').write_text('', encoding='utf-8')
PY

echo "created $TASK_DIR"
