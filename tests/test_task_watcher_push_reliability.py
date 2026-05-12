from __future__ import annotations

import os
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TASK_WATCHER = REPO_ROOT / "scripts" / "task-watcher.sh"
WATCHDOG = REPO_ROOT / "scripts" / "task-watcher-watchdog.sh"


def _base_env(tmp_path: Path) -> dict[str, str]:
    env = os.environ.copy()
    workspace_root = tmp_path / "workspace"
    state_dir = workspace_root / ".runtime" / "state" / "task-watcher"
    log_dir = workspace_root / ".runtime" / "logs"
    workspace_root.mkdir(parents=True, exist_ok=True)
    (workspace_root / "config.json").write_text("{}", encoding="utf-8")
    env.update(
        {
            "WORKSPACE_ROOT": str(workspace_root),
            "TASK_WATCHER_TEST_MODE": "1",
            "STATE_DIR": str(state_dir),
            "LOG_DIR": str(log_dir),
            "LOG_FILE": str(log_dir / "task-watcher.log"),
            "WATCHER_STDOUT_LOG": str(log_dir / "task-watcher.log"),
            "CONFIG_PATH": str(workspace_root / "config.json"),
            "NOTIFY_RETRY_COOLDOWN_SECONDS": "0",
            "RESEND_COOLDOWN_SECONDS": "0",
        }
    )
    return env


def test_task_watcher_scripts_pass_shell_syntax_check():
    subprocess.run(["bash", "-n", str(TASK_WATCHER)], check=True)
    subprocess.run(["bash", "-n", str(WATCHDOG)], check=True)


def test_push_failure_keeps_event_retryable(tmp_path: Path):
    env = _base_env(tmp_path)
    artifact = tmp_path / "result.json"
    artifact.write_text('{"summary":"ok"}\n', encoding="utf-8")

    script = f"""
set -e
source '{TASK_WATCHER}'
push_attempts=0
push_task_event() {{
  push_attempts=$((push_attempts + 1))
  if [ "$push_attempts" -eq 1 ]; then
    return 1
  fi
  return 0
}}

push_task_event_with_retry 'task-1_result_push' '{artifact}' '【进入审查】' 'task-1' '摘要' '下一步' || true
test ! -f "$STATE_DIR/task-1_result_push"
test -f "$STATE_DIR/task-1_result_push.retry"

push_task_event_with_retry 'task-1_result_push' '{artifact}' '【进入审查】' 'task-1' '摘要' '下一步'
test -f "$STATE_DIR/task-1_result_push"
test ! -f "$STATE_DIR/task-1_result_push.retry"
"""

    subprocess.run(["bash", "-lc", script], check=True, env=env)


def test_main_event_routes_use_retry_helpers():
    content = TASK_WATCHER.read_text(encoding="utf-8")

    assert 'push_task_event_with_retry "$result_push_key"' in content
    assert 'push_task_event_with_signature_retry "$review_push_key"' in content
    assert 'push_task_event_with_retry "$verify_push_key"' in content
    assert 'push_task_event_with_retry "$done_push_key"' in content


def test_final_done_notification_respects_retry_cooldown(tmp_path: Path):
    env = _base_env(tmp_path)
    env["NOTIFY_RETRY_COOLDOWN_SECONDS"] = "3600"
    task_dir = tmp_path / "task-1"
    task_dir.mkdir(parents=True, exist_ok=True)
    (task_dir / "task.json").write_text(
        '{\n'
        '  "id": "task-1",\n'
        '  "status": "done",\n'
        '  "task_type": "development",\n'
        '  "execution_mode": "dev",\n'
        '  "target_environment": "dev",\n'
        '  "downstream_action": "review",\n'
        '  "result_summary": "已完成"\n'
        '}\n',
        encoding="utf-8",
    )
    (task_dir / "transitions.jsonl").write_text(
        '{"from":"ready_for_merge","to":"done","at":"2099-01-01T00:00:00+08:00","reason":"test"}\n',
        encoding="utf-8",
    )

    script = f"""
set -e
source '{TASK_WATCHER}'
WATCHER_STARTED_AT_EPOCH=0
push_attempts=0
push_task_event() {{
  push_attempts=$((push_attempts + 1))
  if [ "$push_attempts" -eq 1 ]; then
    return 1
  fi
  return 0
}}

notify_final_done_if_needed '{task_dir}' 'task-1' || true
test ! -f "$STATE_DIR/task-1_done_notice"
test -f "$STATE_DIR/task-1_done_push.retry"
test "$(cat "$STATE_DIR/task-1_done_push.retry")" != ""

notify_final_done_if_needed '{task_dir}' 'task-1' || true
test "$(python3 - <<'PY'\nfrom pathlib import Path\nimport os\nprint(Path(os.environ['STATE_DIR']).joinpath('task-1_done_push.retry').read_text().strip())\nPY\n)" != ""
test ! -f "$STATE_DIR/task-1_done_notice"

echo 0 > "$STATE_DIR/task-1_done_push.retry"
notify_final_done_if_needed '{task_dir}' 'task-1'
test -f "$STATE_DIR/task-1_done_notice"
test -f "$STATE_DIR/task-1_done_push"
test ! -f "$STATE_DIR/task-1_done_push.retry"
"""
    subprocess.run(["bash", "-lc", script], check=True, env=env)


def test_legacy_stdout_log_points_to_authoritative_log(tmp_path: Path):
    env = _base_env(tmp_path)
    script = f"""
set -e
source '{TASK_WATCHER}'
compat_log="$STATE_DIR/task-watcher.stdout.log"
test -L "$compat_log"
python3 - <<'PY'
from pathlib import Path
import os
compat = Path(os.environ["STATE_DIR"]) / "task-watcher.stdout.log"
target = Path(os.environ["LOG_FILE"]).resolve()
assert compat.resolve() == target
PY
"""
    subprocess.run(["bash", "-lc", script], check=True, env=env)


def test_log_writes_once_when_stdout_already_redirected_to_authoritative_log(tmp_path: Path):
    env = _base_env(tmp_path)
    script = f"""
set -e
source '{TASK_WATCHER}'
export TASK_WATCHER_STDOUT_REDIRECTED=1
exec >> "$LOG_FILE" 2>&1
log 'dedupe-check-line'
python3 - <<'PY'
from pathlib import Path
import os
content = Path(os.environ["LOG_FILE"]).read_text(encoding="utf-8")
assert content.count("dedupe-check-line") == 1, content
PY
"""
    subprocess.run(["bash", "-lc", script], check=True, env=env)
