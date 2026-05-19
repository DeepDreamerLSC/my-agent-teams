from __future__ import annotations

import json
import os
import subprocess
import tempfile
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
TASK_WATCHER = REPO_ROOT / "scripts" / "task-watcher.sh"
WATCHDOG = REPO_ROOT / "scripts" / "task-watcher-watchdog.sh"
TEAMCTL = REPO_ROOT / "scripts" / "teamctl.sh"


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


def _write_exec(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


def test_task_watcher_scripts_pass_shell_syntax_check():
    subprocess.run(["bash", "-n", str(TASK_WATCHER)], check=True)
    subprocess.run(["bash", "-n", str(WATCHDOG)], check=True)
    subprocess.run(["bash", "-n", str(TEAMCTL)], check=True)


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
    assert 'push_task_event_with_signature_retry "$done_push_key"' in content


def test_push_feishu_passes_deterministic_uuid_to_push_script(tmp_path: Path):
    env = _base_env(tmp_path)
    push_script = tmp_path / "push.sh"
    uuid_log = tmp_path / "uuid.log"
    _write_exec(
        push_script,
        f'''#!/bin/bash
printf '%s\n' "$FEISHU_MESSAGE_UUID" >> '{uuid_log}'
echo ok
''',
    )

    script = f"""
set -e
source '{TASK_WATCHER}'
PUSH_SCRIPT='{push_script}'
USER_ID='user-1'
push_feishu 'hello' '【任务完成】' 'task-1'
push_feishu 'hello' '【任务完成】' 'task-1'
push_feishu 'hello changed' '【任务完成】' 'task-1'
python3 - <<'PY'
from pathlib import Path
import re
values = Path(r'{uuid_log}').read_text(encoding='utf-8').splitlines()
assert len(values) == 3, values
assert values[0] == values[1], values
assert values[0] != values[2], values
assert all(re.fullmatch(r'[0-9a-f]{{64}}', item) for item in values), values
PY
"""
    subprocess.run(["bash", "-lc", script], check=True, env=env)


def test_reconcile_clean_task_invariants_does_not_rewrite_task_json(tmp_path: Path):
    env = _base_env(tmp_path)
    env["STATE_INVARIANTS_PY"] = str(REPO_ROOT / "scripts" / "lib" / "task_state_invariants.py")
    task_dir = tmp_path / "task-1"
    task_dir.mkdir(parents=True, exist_ok=True)
    task_json = task_dir / "task.json"
    task_json.write_text(
        '{\n'
        '  "id": "task-1",\n'
        '  "status": "done",\n'
        '  "merge_gate_state": "closed"\n'
        '}\n',
        encoding="utf-8",
    )

    script = f"""
set -e
source '{TASK_WATCHER}'
before="$(cat '{task_json}')"
reconcile_task_state_invariants '{task_dir}' 'task-1' >/tmp/reconcile.out
after="$(cat '{task_json}')"
test "$before" = "$after"
"""
    subprocess.run(["bash", "-lc", script], check=True, env=env)


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
test "$(cat "$STATE_DIR/task-1_done_push")" = "task-1:done:4070880000"

python3 - <<'PY'
import json
from pathlib import Path
path = Path(r'{task_dir}') / 'task.json'
payload = json.loads(path.read_text(encoding='utf-8'))
payload['updated_at'] = '2099-01-01T00:00:01+08:00'
payload['state_invariant_checked_at'] = '2099-01-01T00:00:01+08:00'
path.write_text(json.dumps(payload, ensure_ascii=False, indent=2) + '\\n', encoding='utf-8')
PY
notify_final_done_if_needed '{task_dir}' 'task-1'
test "$push_attempts" -eq 2
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


def test_review_queue_clear_only_removes_matching_task(tmp_path: Path):
    env = _base_env(tmp_path)
    workspace_root = Path(env["WORKSPACE_ROOT"])
    tasks_root = workspace_root / "tasks"
    task_a = tasks_root / "task-a"
    task_a.mkdir(parents=True)
    (task_a / "task.json").write_text(
        '{\n'
        '  "id": "task-a",\n'
        '  "status": "ready_for_merge",\n'
        '  "merge_gate_state": "review_pending",\n'
        '  "reviewer": "review-1",\n'
        '  "reviewers": ["review-1"]\n'
        '}\n',
        encoding="utf-8",
    )

    script = f"""
set -e
source '{TASK_WATCHER}'
queue_state_set review review-1 task-b
clear_review_queue_state_for_task '{task_a}'
python3 - <<'PY'
import json
from pathlib import Path
import os
state = Path(os.environ["STATE_DIR"]) / "review-queue-review-1.json"
assert json.loads(state.read_text(encoding="utf-8"))["task_id"] == "task-b"
PY

queue_state_set review review-1 task-a
clear_review_queue_state_for_task '{task_a}'
test ! -f "$STATE_DIR/review-queue-review-1.json"
"""
    subprocess.run(["bash", "-lc", script], check=True, env=env)


def test_qa_queue_clear_only_removes_matching_task(tmp_path: Path):
    env = _base_env(tmp_path)
    workspace_root = Path(env["WORKSPACE_ROOT"])
    Path(env["CONFIG_PATH"]).write_text(
        '{\n  "agents": {"qa-1": {"role": "qa"}}\n}\n',
        encoding="utf-8",
    )
    tasks_root = workspace_root / "tasks"
    task_a = tasks_root / "task-a"
    task_a.mkdir(parents=True)
    (task_a / "task.json").write_text(
        '{\n'
        '  "id": "task-a",\n'
        '  "status": "ready_for_merge",\n'
        '  "merge_gate_state": "qa_pending"\n'
        '}\n',
        encoding="utf-8",
    )

    script = f"""
set -e
source '{TASK_WATCHER}'
queue_state_set qa qa-1 task-b
clear_qa_queue_state_for_task 'task-a'
python3 - <<'PY'
import json
from pathlib import Path
import os
state = Path(os.environ["STATE_DIR"]) / "qa-queue-qa-1.json"
assert json.loads(state.read_text(encoding="utf-8"))["task_id"] == "task-b"
PY

queue_state_set qa qa-1 task-a
clear_qa_queue_state_for_task 'task-a'
test ! -f "$STATE_DIR/qa-queue-qa-1.json"
"""
    subprocess.run(["bash", "-lc", script], check=True, env=env)


def test_reserved_timeout_returns_task_to_pool(tmp_path: Path):
    env = _base_env(tmp_path)
    env["DISPATCH_RESEND_AFTER_SECONDS"] = "1"
    workspace_root = Path(env["WORKSPACE_ROOT"])
    task_dir = workspace_root / "tasks" / "reserved-task"
    task_dir.mkdir(parents=True)
    (task_dir / "task.json").write_text(
        '{\n'
        '  "id": "reserved-task",\n'
        '  "status": "dispatched",\n'
        '  "assigned_agent": "dev-1",\n'
        '  "pre_claim_assigned_agent": "auto",\n'
        '  "pool_entered_at": "2026-05-09T10:00:00+08:00",\n'
        '  "claimed_by": "dev-1",\n'
        '  "claimed_at": "2026-05-09T10:01:00+08:00",\n'
        '  "reserved_by": "dev-1",\n'
        '  "reserved_at": "2026-05-09T10:01:00+08:00",\n'
        '  "lease_acquired_at": "2000-01-01T00:00:00+08:00"\n'
        '}\n',
        encoding="utf-8",
    )
    (task_dir / "transitions.jsonl").write_text("", encoding="utf-8")
    (task_dir / "claim.json").write_text('{"agent":"dev-1"}\n', encoding="utf-8")

    script = f"""
set -e
source '{TASK_WATCHER}'
return_reserved_to_pool_if_timed_out '{task_dir}' 'reserved-task'
python3 - <<'PY'
import json
from pathlib import Path
task_dir = Path('{task_dir}')
task = json.loads((task_dir / 'task.json').read_text(encoding='utf-8'))
assert task['status'] == 'pooled', task
assert task['assigned_agent'] == 'auto', task
assert 'reserved_by' not in task, task
assert list(task_dir.glob('claim.expired.*.json'))
assert 'to":"pooled"' in (task_dir / 'transitions.jsonl').read_text(encoding='utf-8').replace(' ', '')
PY
"""
    subprocess.run(["bash", "-lc", script], check=True, env=env)


def test_dispatch_failure_threshold_trips_after_three_control_plane_failures(tmp_path: Path):
    env = _base_env(tmp_path)
    workspace_root = Path(env["WORKSPACE_ROOT"])
    task_dir = workspace_root / "tasks" / "dispatch-fail-task"
    task_dir.mkdir(parents=True)
    (task_dir / "task.json").write_text(
        '{\n'
        '  "id": "dispatch-fail-task",\n'
        '  "status": "dispatched",\n'
        '  "assigned_agent": "dev-1"\n'
        '}\n',
        encoding="utf-8",
    )
    (task_dir / "transitions.jsonl").write_text("", encoding="utf-8")

    script = f"""
set -e
source '{TASK_WATCHER}'
record_dispatch_delivery_attempt '{task_dir}' 'delivery_failed' '1' 'first failure' 'idle_session'
record_dispatch_delivery_attempt '{task_dir}' 'session_unhealthy' '1' 'second failure' 'missing_session'
record_dispatch_delivery_attempt '{task_dir}' 'delivery_failed' '1' 'third failure' 'idle_session'
dispatch_failure_threshold_exceeded '{task_dir}'
python3 - <<'PY'
import json
from pathlib import Path
task = json.loads(Path('{task_dir}/task.json').read_text(encoding='utf-8'))
assert task['dispatch_delivery_retry_count'] == 3, task
assert task['dispatch_delivery_consecutive_failures'] == 3, task
assert task['control_plane_state'] == 'delivery_failed', task
PY
"""
    subprocess.run(["bash", "-lc", script], check=True, env=env)


def test_requeue_dispatched_task_to_pool_tracks_auto_requeue(tmp_path: Path):
    env = _base_env(tmp_path)
    workspace_root = Path(env["WORKSPACE_ROOT"])
    task_dir = workspace_root / "tasks" / "requeue-task"
    task_dir.mkdir(parents=True)
    (task_dir / "task.json").write_text(
        '{\n'
        '  "id": "requeue-task",\n'
        '  "status": "dispatched",\n'
        '  "assigned_agent": "dev-1",\n'
        '  "pre_claim_assigned_agent": "auto",\n'
        '  "claim_policy": "pull",\n'
        '  "claimed_by": "dev-1",\n'
        '  "reserved_by": "dev-1"\n'
        '}\n',
        encoding="utf-8",
    )
    (task_dir / "transitions.jsonl").write_text("", encoding="utf-8")
    (task_dir / "claim.json").write_text('{"agent":"dev-1"}\n', encoding="utf-8")

    script = f"""
set -e
source '{TASK_WATCHER}'
requeue_dispatched_task_to_pool '{task_dir}' 'requeue-task' 'control-plane threshold reached'
python3 - <<'PY'
import json
from pathlib import Path
task_dir = Path('{task_dir}')
task = json.loads((task_dir / 'task.json').read_text(encoding='utf-8'))
assert task['status'] == 'pooled', task
assert task['assigned_agent'] == 'auto', task
assert task['auto_requeue_count'] == 1, task
assert task['control_plane_state'] == 'auto_requeue', task
assert list(task_dir.glob('claim.requeued.*.json'))
PY
"""
    subprocess.run(["bash", "-lc", script], check=True, env=env)


def test_reassign_dispatched_task_switches_agent_after_control_plane_failure(tmp_path: Path):
    env = _base_env(tmp_path)
    workspace_root = Path(env["WORKSPACE_ROOT"])
    dev_root = workspace_root / "dev"
    dev_root.mkdir(parents=True, exist_ok=True)
    config_path = Path(env["CONFIG_PATH"])
    config_path.write_text(json.dumps({
        "agents": {
            "dev-1": {"role": "fullstack_dev"},
            "dev-2": {"role": "fullstack_dev"},
        },
        "projects": {
            "demo": {"dev_root": str(dev_root)},
        },
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    send_script = workspace_root / "send-stub.sh"
    _write_exec(send_script, '#!/bin/bash\necho "delivered to $1 (runtime=codex, attempt=1)"\n')
    env["SEND_SCRIPT"] = str(send_script)
    env["REASSIGN_TASK_SCRIPT"] = str(REPO_ROOT / "scripts" / "reassign-task.sh")

    task_dir = workspace_root / "tasks" / "reassign-task"
    task_dir.mkdir(parents=True)
    (task_dir / "task.json").write_text(json.dumps({
        "id": "reassign-task",
        "status": "dispatched",
        "assigned_agent": "dev-1",
        "claim_policy": "pull",
        "claim_scope": ["dev-1", "dev-2"],
        "project": "demo",
        "task_type": "development",
        "domain": "development",
        "execution_mode": "dev",
        "target_environment": "dev",
        "read_only": False,
        "write_scope": [str(dev_root / "src" / "worker.ts")],
        "review_required": True,
        "test_required": True,
        "quality_gate_mode": "parallel",
        "claimed_by": "dev-1",
        "claimed_at": "2026-05-18T10:00:00+08:00",
        "reserved_by": "dev-1",
        "reserved_at": "2026-05-18T10:00:00+08:00",
        "pre_claim_assigned_agent": "auto",
        "pool_entered_at": "2026-05-18T09:55:00+08:00",
    }, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (task_dir / "transitions.jsonl").write_text("", encoding="utf-8")

    script = f"""
set -e
tmux() {{
  if [ "$1" = "has-session" ]; then
    [ "$3" = "dev-2" ] && return 0
    return 1
  fi
  if [ "$1" = "capture-pane" ]; then
    return 0
  fi
  if [ "$1" = "send-keys" ]; then
    return 0
  fi
  return 0
}}
source '{TASK_WATCHER}'
reassign_dispatched_task '{task_dir}' 'reassign-task' 'dev-1' 'dev-2' 'threshold reached'
python3 - <<'PY'
import json
from pathlib import Path
task = json.loads(Path('{task_dir}/task.json').read_text(encoding='utf-8'))
assert task['assigned_agent'] == 'dev-2', task
assert task['reassign_count'] == 1, task
assert task['control_plane_state'] == 'reassigned', task
assert task['dispatch_delivery_attempt_count'] == 1, task
PY
"""
    subprocess.run(["bash", "-lc", script], check=True, env=env)


def test_record_dependencies_ready_persists_exact_watcher_boundary(tmp_path: Path):
    env = _base_env(tmp_path)
    workspace_root = Path(env["WORKSPACE_ROOT"])
    tasks_root = workspace_root / "tasks"
    dep_dir = tasks_root / "dep-task"
    task_dir = tasks_root / "pooled-task"
    dep_dir.mkdir(parents=True)
    task_dir.mkdir(parents=True)
    (dep_dir / "task.json").write_text('{"id":"dep-task","status":"done"}\n', encoding="utf-8")
    (task_dir / "task.json").write_text(
        '{\n'
        '  "id": "pooled-task",\n'
        '  "status": "pooled",\n'
        '  "depends_on": ["dep-task"],\n'
        '  "dependency_policy": "done_only"\n'
        '}\n',
        encoding="utf-8",
    )
    (task_dir / "transitions.jsonl").write_text("", encoding="utf-8")

    script = f"""
set -e
source '{TASK_WATCHER}'
record_dependencies_ready_if_needed '{task_dir}' 'pooled-task'
python3 - <<'PY'
import json
from pathlib import Path
task_dir = Path('{task_dir}')
task = json.loads((task_dir / 'task.json').read_text(encoding='utf-8'))
assert task.get('dependencies_ready_at'), task
transition_text = (task_dir / 'transitions.jsonl').read_text(encoding='utf-8')
assert 'dependencies_ready' in transition_text, transition_text
PY
"""
    subprocess.run(["bash", "-lc", script], check=True, env=env)


class TaskWatcherStaleArtifactTests(unittest.TestCase):
    def test_pending_stale_review_does_not_clear_review_queue_assignment(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            env = _base_env(tmp_path)
            task_dir = tmp_path / "task-stale-review"
            task_dir.mkdir(parents=True)
            (task_dir / "task.json").write_text(
                '{\n'
                '  "id": "task-stale-review",\n'
                '  "status": "ready_for_merge",\n'
                '  "merge_gate_state": "review_pending",\n'
                '  "reviewer": "review-1",\n'
                '  "review_required": true,\n'
                '  "execution_round": 2\n'
                '}\n',
                encoding="utf-8",
            )
            (task_dir / "result.json").write_text(
                '{\n'
                '  "task_id": "task-stale-review",\n'
                '  "agent": "dev-1",\n'
                '  "status": "success",\n'
                '  "round": 2,\n'
                '  "summary": "new result"\n'
                '}\n',
                encoding="utf-8",
            )
            (task_dir / "review.json").write_text(
                '{\n'
                '  "task_id": "task-stale-review",\n'
                '  "reviewer": "review-1",\n'
                '  "status": "request_changes",\n'
                '  "round": 1,\n'
                '  "summary": "old review"\n'
                '}\n',
                encoding="utf-8",
            )

            script = f"""
set -e
source '{TASK_WATCHER}'
queue_state_set review review-1 task-stale-review
state="$(review_state '{task_dir}' '')"
test "$state" = "pending"
case "$state" in
  invalid|pass|fail) clear_review_queue_state_for_task '{task_dir}' ;;
esac
test -f "$STATE_DIR/review-queue-review-1.json"
"""
            subprocess.run(["bash", "-lc", script], check=True, env=env)

    def test_stale_verify_is_missing_for_watcher_state(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            env = _base_env(tmp_path)
            task_dir = tmp_path / "task-stale-verify"
            task_dir.mkdir(parents=True)
            (task_dir / "task.json").write_text(
                '{\n'
                '  "id": "task-stale-verify",\n'
                '  "status": "ready_for_merge",\n'
                '  "merge_gate_state": "qa_pending",\n'
                '  "test_required": true,\n'
                '  "execution_round": 2\n'
                '}\n',
                encoding="utf-8",
            )
            (task_dir / "result.json").write_text(
                '{\n'
                '  "task_id": "task-stale-verify",\n'
                '  "agent": "dev-1",\n'
                '  "status": "success",\n'
                '  "round": 2,\n'
                '  "summary": "new result"\n'
                '}\n',
                encoding="utf-8",
            )
            (task_dir / "verify.json").write_text(
                '{\n'
                '  "task_id": "task-stale-verify",\n'
                '  "tester": "qa-1",\n'
                '  "status": "pass",\n'
                '  "round": 1,\n'
                '  "summary": "old qa pass"\n'
                '}\n',
                encoding="utf-8",
            )

            script = f"""
set -e
source '{TASK_WATCHER}'
test "$(verify_state '{task_dir}/verify.json')" = "missing"
test "$(resolve_merge_gate_state '{task_dir}')" = "qa_pending"
"""
            subprocess.run(["bash", "-lc", script], check=True, env=env)


class TaskWatcherParallelQualityGateTests(unittest.TestCase):
    def test_resolve_merge_gate_state_supports_quality_pending(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            env = _base_env(tmp_path)
            task_dir = tmp_path / "task-quality-pending"
            task_dir.mkdir(parents=True)
            (task_dir / "task.json").write_text(
                '{\n'
                '  "id": "task-quality-pending",\n'
                '  "status": "ready_for_merge",\n'
                '  "review_required": true,\n'
                '  "test_required": true,\n'
                '  "quality_gate_mode": "parallel",\n'
                '  "merge_gate_state": "quality_pending"\n'
                '}\n',
                encoding="utf-8",
            )
            script = f"""
set -e
source '{TASK_WATCHER}'
test "$(resolve_merge_gate_state '{task_dir}')" = "quality_pending"
"""
            subprocess.run(["bash", "-lc", script], check=True, env=env)

    def test_parallel_qa_pass_does_not_auto_close_before_review(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            env = _base_env(tmp_path)
            task_dir = tmp_path / "task-parallel-gate"
            task_dir.mkdir(parents=True)
            (task_dir / "task.json").write_text(
                '{\n'
                '  "id": "task-parallel-gate",\n'
                '  "status": "ready_for_merge",\n'
                '  "review_required": true,\n'
                '  "test_required": true,\n'
                '  "quality_gate_mode": "parallel",\n'
                '  "merge_gate_state": "quality_pending"\n'
                '}\n',
                encoding="utf-8",
            )
            (task_dir / "verify.json").write_text(
                '{\n'
                '  "task_id": "task-parallel-gate",\n'
                '  "tester": "qa-1",\n'
                '  "status": "pass",\n'
                '  "summary": "qa pass"\n'
                '}\n',
                encoding="utf-8",
            )
            script = f"""
set -e
source '{TASK_WATCHER}'
set_task_gate_state '{task_dir}' 'ready_for_merge' 'test qa pass only' 'quality_pending' '' 'qa' '2026-05-16T10:00:00+08:00' '__KEEP__' 'passed'
python3 - <<'PY'
import json
from pathlib import Path
task = json.loads(Path('{task_dir}/task.json').read_text(encoding='utf-8'))
assert task['status'] == 'ready_for_merge', task
assert task['merge_gate_state'] == 'quality_pending', task
assert task['qa_gate_state'] == 'passed', task
assert task.get('review_gate_state') in (None, 'pending'), task
PY
"""
            subprocess.run(["bash", "-lc", script], check=True, env=env)

    def test_parallel_quality_gate_both_complete_promotes_pm_acceptance(self):
        with tempfile.TemporaryDirectory() as tmp:
            tmp_path = Path(tmp)
            env = _base_env(tmp_path)
            task_dir = tmp_path / "task-parallel-complete"
            task_dir.mkdir(parents=True)
            (task_dir / "task.json").write_text(
                '{\n'
                '  "id": "task-parallel-complete",\n'
                '  "status": "ready_for_merge",\n'
                '  "review_required": true,\n'
                '  "test_required": true,\n'
                '  "quality_gate_mode": "parallel",\n'
                '  "merge_gate_state": "quality_pending",\n'
                '  "review_gate_state": "approved",\n'
                '  "qa_gate_state": "pending"\n'
                '}\n',
                encoding="utf-8",
            )
            script = f"""
set -e
source '{TASK_WATCHER}'
set_task_gate_state '{task_dir}' 'ready_for_merge' 'test all quality gates done' 'pm_acceptance_pending' '' 'qa' '2026-05-16T10:05:00+08:00' '__KEEP__' 'passed'
python3 - <<'PY'
import json
from pathlib import Path
task = json.loads(Path('{task_dir}/task.json').read_text(encoding='utf-8'))
assert task['status'] == 'ready_for_merge', task
assert task['merge_gate_state'] == 'pm_acceptance_pending', task
assert task['review_gate_state'] == 'approved', task
assert task['qa_gate_state'] == 'passed', task
PY
"""
            subprocess.run(["bash", "-lc", script], check=True, env=env)
