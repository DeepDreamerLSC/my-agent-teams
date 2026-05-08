#!/bin/bash
set -euo pipefail

TASK_DIR=""
SUMMARY=""
REASON="manual close via close-task.sh"
DRY_RUN=0

usage() {
  cat <<'USAGE'
usage: close-task.sh --task-dir <task-dir> [--summary <summary>] [--reason <reason>] [--dry-run]

Options:
  --task-dir   任务目录绝对路径（必须包含 task.json）
  --summary    写回 task.json.result_summary 的摘要
  --reason     记录到 transitions.jsonl 的原因（默认: manual close via close-task.sh）
  --dry-run    仅展示将要执行的变更，不落盘
  -h, --help   显示帮助
USAGE
}

while [ $# -gt 0 ]; do
  case "$1" in
    --task-dir)
      TASK_DIR="${2:-}"
      shift 2
      ;;
    --summary)
      SUMMARY="${2:-}"
      shift 2
      ;;
    --reason)
      REASON="${2:-}"
      shift 2
      ;;
    --dry-run)
      DRY_RUN=1
      shift
      ;;
    -h|--help)
      usage
      exit 0
      ;;
    *)
      echo "unknown option: $1" >&2
      usage >&2
      exit 2
      ;;
  esac
done

if [ -z "$TASK_DIR" ]; then
  echo "missing required option: --task-dir" >&2
  usage >&2
  exit 2
fi

python3 - "$TASK_DIR" "$SUMMARY" "$REASON" "$DRY_RUN" <<'PY'
import json
import os
import re
import sys
import tempfile
from datetime import datetime
from pathlib import Path


def fail(message: str, exit_code: int = 1) -> None:
    print(message, file=sys.stderr)
    raise SystemExit(exit_code)


def load_json(path: Path) -> dict:
    try:
        return json.loads(path.read_text(encoding='utf-8'))
    except FileNotFoundError:
        fail(f'missing file: {path}')
    except json.JSONDecodeError as exc:
        fail(f'invalid json: {path}: {exc}')


CONCLUSION_LABEL_RE = re.compile(
    r'^\s*(?:#{1,6}\s*)?'
    r'(?:审查结论|复审结论|最终结论|最终意见|结论|review conclusion|conclusion|verdict|decision)'
    r'\s*(?:[:：\-—]\s*)?(.*)$',
    re.IGNORECASE,
)
APPROVE_PATTERNS = (
    re.compile(r'\bapprove(?:d)?\b', re.IGNORECASE),
    re.compile(r'\blgtm\b', re.IGNORECASE),
    re.compile(r'\bship\s+it\b', re.IGNORECASE),
    re.compile(r'通过|同意合入|批准|可以合入'),
)
REJECT_PATTERNS = (
    re.compile(r'\brequest\s+changes\b', re.IGNORECASE),
    re.compile(r'\bchanges\s+requested\b', re.IGNORECASE),
    re.compile(r'\breject(?:ed)?\b', re.IGNORECASE),
    re.compile(r'驳回|不通过|未通过|不接受|请求修改|要求修改'),
)


def classify_review_snippet(snippet: str) -> str:
    """Classify an explicit review verdict snippet.

    Review files often mention state names such as ``review_rejected`` or
    ``qa_failed`` in explanatory text.  Those must not override an explicit
    APPROVE conclusion, so matching is limited to conclusion snippets and
    English reject words require token boundaries instead of substring scans.
    """
    if not snippet.strip():
        return 'pending'
    if any(pattern.search(snippet) for pattern in REJECT_PATTERNS):
        return 'fail'
    if any(pattern.search(snippet) for pattern in APPROVE_PATTERNS):
        return 'pass'
    return 'pending'


def classify_review_text(text: str) -> str:
    lines = text.splitlines()

    # Prefer explicit verdict/conclusion sections.  For heading-only forms
    # such as "## 结论", inspect only the next few non-empty lines rather
    # than the whole review body.
    for index, line in enumerate(lines[:60]):
        match = CONCLUSION_LABEL_RE.match(line)
        if not match:
            continue
        snippets = []
        suffix = match.group(1).strip()
        if suffix:
            snippets.append(suffix)
        for following in lines[index + 1:index + 8]:
            stripped = following.strip()
            if not stripped:
                continue
            if stripped.startswith('#') and snippets:
                break
            snippets.append(stripped)
            if len(snippets) >= 4:
                break
        state = classify_review_snippet('\n'.join(snippets))
        if state != 'pending':
            return state

    # Backward-compatible fallback for old terse review files that only put
    # APPROVE / REQUEST CHANGES near the top.  Do not scan the full document.
    first_nonempty_lines = [line.strip() for line in lines if line.strip()][:20]
    return classify_review_snippet('\n'.join(first_nonempty_lines))


def parse_review_file(path: Path) -> str:
    if not path.exists():
        return 'missing'
    text = path.read_text(encoding='utf-8', errors='ignore')
    return classify_review_text(text)


def parse_review_state(task_dir: Path, review_level: str) -> str:
    review_main_state = parse_review_file(task_dir / 'review.md')
    if review_level == 'complex':
        design_state = parse_review_file(task_dir / 'design-review.md')
        if review_main_state == 'fail' or design_state == 'fail':
            return 'fail'
        if review_main_state == 'pass' and design_state == 'pass':
            return 'pass'
        return 'pending'
    if review_main_state == 'fail':
        return 'fail'
    if review_main_state == 'pass':
        return 'pass'
    return 'pending'


def parse_verify_state(task_dir: Path) -> str:
    path = task_dir / 'verify.json'
    if not path.exists():
        return 'missing'
    payload = load_json(path)
    values = [
        payload.get('pass'),
        payload.get('ok'),
        payload.get('result'),
        payload.get('status'),
        payload.get('verdict'),
        payload.get('conclusion'),
    ]
    for value in values:
        if isinstance(value, bool):
            return 'pass' if value else 'fail'
        if value is None:
            continue
        normalized = str(value).strip().lower()
        if normalized in {'pass', 'passed', 'approve', 'approved', 'ok', 'true', '1', 'success', 'done'}:
            return 'pass'
        if normalized in {'fail', 'failed', 'false', '0', 'reject', 'rejected', 'error', 'blocked'}:
            return 'fail'
    return 'pending'


task_dir = Path(sys.argv[1]).expanduser().resolve()
summary_arg = sys.argv[2]
reason = sys.argv[3].strip() or 'manual close via close-task.sh'
dry_run = sys.argv[4] == '1'

task_json_path = task_dir / 'task.json'
transitions_path = task_dir / 'transitions.jsonl'

if not task_dir.is_dir():
    fail(f'task directory not found: {task_dir}')
if not task_json_path.exists():
    fail(f'missing file: {task_json_path}')

task = load_json(task_json_path)
current_status = str(task.get('status') or '')
if current_status != 'ready_for_merge':
    fail(f'task status must be ready_for_merge, got: {current_status or "<empty>"}')

review_required = bool(task.get('review_required'))
test_required = bool(task.get('test_required'))
review_level = str(task.get('review_level') or '').strip().lower()
merge_gate_state = str(task.get('merge_gate_state') or '').strip()
review_state = parse_review_state(task_dir, review_level)
verify_state = parse_verify_state(task_dir)

if merge_gate_state == 'review_pending' and not (review_required and review_state == 'pass'):
    fail(f'task merge_gate_state still pending: {merge_gate_state}')
# QA pass is represented by verify.json.  task-watcher may invoke this script
# while task.json still says qa_pending, so allow that single pending gate only
# when the current verify artifact has already passed.
if merge_gate_state == 'qa_pending' and not (test_required and verify_state == 'pass'):
    fail(f'task merge_gate_state still pending: {merge_gate_state}')
if merge_gate_state in {'review_rejected', 'qa_failed'}:
    fail(f'task merge_gate_state is rejected/failed: {merge_gate_state}')
if review_required and review_state != 'pass':
    fail(f'review is not approved: {review_state}')
if test_required and verify_state != 'pass':
    fail(f'qa verify is not passed: {verify_state}')

summary = summary_arg.strip() if summary_arg.strip() else str(task.get('result_summary') or '').strip()
if not summary:
    fail('result_summary is empty; provide --summary or ensure task.json.result_summary already has a value')

now = datetime.now().astimezone().isoformat(timespec='seconds')
transition = {
    'from': 'ready_for_merge',
    'to': 'done',
    'at': now,
    'reason': reason,
}
updated_task = dict(task)
updated_task['status'] = 'done'
updated_task['updated_at'] = now
updated_task['result_summary'] = summary
updated_task['merge_gate_state'] = 'closed'
updated_task['rework_reason'] = None
updated_task['last_gate_actor'] = 'watcher' if 'watcher' in reason else 'pm-chief'
updated_task['last_gate_decision_at'] = now

preview = {
    'task_dir': str(task_dir),
    'dry_run': dry_run,
    'status_before': current_status,
    'status_after': 'done',
    'updated_at': now,
    'result_summary': summary,
    'review_state': review_state,
    'verify_state': verify_state,
    'merge_gate_state_after': 'closed',
    'transition': transition,
}
print(json.dumps(preview, ensure_ascii=False, indent=2))

if dry_run:
    raise SystemExit(0)

with tempfile.NamedTemporaryFile('w', delete=False, dir=str(task_json_path.parent), encoding='utf-8') as tmp:
    json.dump(updated_task, tmp, ensure_ascii=False, indent=2)
    tmp.write('\n')
tmp_path = Path(tmp.name)
os.replace(tmp_path, task_json_path)
with transitions_path.open('a', encoding='utf-8') as fp:
    fp.write(json.dumps(transition, ensure_ascii=False) + '\n')
PY
