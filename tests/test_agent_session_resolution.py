from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
AGENT_CONFIG = REPO_ROOT / "scripts" / "lib" / "agent_config.py"
GEN_REPORT = REPO_ROOT / "scripts" / "_gen_report.py"
SEND_TO_AGENT = REPO_ROOT / "scripts" / "send-to-agent.sh"
SEND_CHAT = REPO_ROOT / "scripts" / "send-chat.sh"
POOL_TASK = REPO_ROOT / "scripts" / "pool-task.sh"
RESUME_TASK = REPO_ROOT / "scripts" / "resume-task.sh"
REASSIGN_TASK = REPO_ROOT / "scripts" / "reassign-task.sh"
CLOSE_TASK = REPO_ROOT / "scripts" / "close-task.sh"
CHAT_METRICS = REPO_ROOT / "scripts" / "chat-metrics.py"
PM_CHAT_CHECK = REPO_ROOT / "scripts" / "pm-chat-check.sh"
AGENT_AVAILABILITY = REPO_ROOT / "scripts" / "lib" / "agent_availability.sh"
TASK_WATCHER = REPO_ROOT / "scripts" / "task-watcher.sh"
TASK_STATE_INVARIANTS = REPO_ROOT / "scripts" / "lib" / "task_state_invariants.py"


def _write_config(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "agents": {
                    "dev-1": {
                        "role": "fullstack_dev",
                        "runtime": "codex",
                        "tmux_session": "tmux-dev-custom",
                    },
                    "qa-1": {
                        "role": "qa",
                        "runtime": "claude_code",
                        "tmux_session": "tmux-qa-custom",
                    },
                }
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def _write_medium_config(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "orchestration": {"root_pm": "pm-chief"},
                "agents": {
                    "pm-chief": {"role": "pm", "tmux_session": "pm-custom"},
                    "arch-1": {"role": "architect", "tmux_session": "arch-custom"},
                    "dev-1": {"role": "fullstack_dev", "tmux_session": "dev-one-custom"},
                    "dev-2": {"role": "fullstack_dev", "tmux_session": "dev-two-custom"},
                    "dev-3": {"role": "fullstack_dev", "tmux_session": "dev-three-custom"},
                    "qa-1": {"role": "qa", "tmux_session": "qa-custom"},
                    "review-1": {"role": "reviewer", "tmux_session": "review-custom"},
                }
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def _fake_tmux(tmp_path: Path) -> tuple[Path, Path]:
    bin_dir = tmp_path / "bin"
    bin_dir.mkdir()
    log_path = tmp_path / "tmux-calls.log"
    tmux = bin_dir / "tmux"
    tmux.write_text(
        f"""#!/bin/bash
printf '%s\\n' "$*" >> '{log_path}'
case "$1" in
  has-session)
    [ "$3" = "tmux-dev-custom" ] || [ "$3" = "tmux-qa-custom" ]
    ;;
  capture-pane)
    printf 'Working pane-%s-%s\\n' "$3" "$RANDOM"
    ;;
  show-environment)
    [ "$3" = "tmux-dev-custom" ] || [ "$3" = "tmux-qa-custom" ]
    ;;
  send-keys)
    exit 0
    ;;
  *)
    exit 0
    ;;
esac
""",
        encoding="utf-8",
    )
    tmux.chmod(0o755)
    return bin_dir, log_path


def _write_custom_pm_config(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "orchestration": {"root_pm": "pm-alt"},
                "agents": {
                    "pm-alt": {
                        "role": "pm",
                        "runtime": "claude_code",
                        "tmux_session": "tmux-pm-custom",
                    },
                    "dev-1": {
                        "role": "fullstack_dev",
                        "runtime": "codex",
                        "tmux_session": "tmux-dev-custom",
                    },
                },
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def _write_custom_role_defaults_config(path: Path) -> None:
    path.write_text(
        json.dumps(
            {
                "orchestration": {
                    "root_pm": "lead-pm",
                    "integration_owner": "principal-architect",
                },
                "domain_policies": {
                    "development": {
                        "default_reviewer": "quality-reviewer",
                        "default_tester": "release-qa",
                    }
                },
                "agents": {
                    "lead-pm": {"role": "pm", "tmux_session": "pm-pane"},
                    "principal-architect": {"role": "architect", "tmux_session": "architect-pane"},
                    "builder-a": {"role": "fullstack_dev", "tmux_session": "builder-pane"},
                    "release-qa": {"role": "qa", "tmux_session": "qa-pane"},
                    "quality-reviewer": {"role": "reviewer", "tmux_session": "review-pane"},
                },
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )


def test_agent_config_resolves_custom_tmux_session(tmp_path: Path):
    config_path = tmp_path / "config.json"
    _write_config(config_path)

    completed = subprocess.run(
        [sys.executable, str(AGENT_CONFIG), "resolve-target", "dev-1", "--config", str(config_path)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=True,
    )

    assert completed.stdout.strip() == "dev-1\ttmux-dev-custom\tcodex"


def test_agent_config_resolves_root_pm_from_config(tmp_path: Path):
    config_path = tmp_path / "config.json"
    _write_custom_pm_config(config_path)

    completed = subprocess.run(
        [sys.executable, str(AGENT_CONFIG), "root-pm", "--config", str(config_path)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=True,
    )

    assert completed.stdout.strip() == "pm-alt"


def test_agent_config_resolves_custom_role_defaults(tmp_path: Path):
    config_path = tmp_path / "config.json"
    _write_custom_role_defaults_config(config_path)

    def run(command: str, *args: str) -> list[str]:
        completed = subprocess.run(
            [sys.executable, str(AGENT_CONFIG), command, "--config", str(config_path), *args],
            cwd=str(REPO_ROOT),
            capture_output=True,
            text=True,
            check=True,
        )
        return completed.stdout.splitlines()

    assert run("root-pm") == ["lead-pm"]
    assert run("integration-owner") == ["principal-architect"]
    assert run("default-reviewer", "--domain", "development") == ["quality-reviewer"]
    assert run("default-reviewers", "--domain", "development", "--review-level", "complex") == [
        "quality-reviewer",
        "principal-architect",
    ]
    assert run("default-tester", "--domain", "development") == ["release-qa"]
    assert run("list-review-agent-ids") == ["principal-architect", "quality-reviewer"]
    assert run("list-qa-agent-ids") == ["release-qa"]


def test_agent_config_lists_current_team_profile_agents(tmp_path: Path):
    config_path = tmp_path / "config.json"
    _write_medium_config(config_path)

    ids = subprocess.run(
        [sys.executable, str(AGENT_CONFIG), "list-agent-ids", "--config", str(config_path)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=True,
    ).stdout.strip()
    labels = subprocess.run(
        [sys.executable, str(AGENT_CONFIG), "role-labels-json", "--config", str(config_path)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=True,
    ).stdout

    assert ids == "pm-chief,arch-1,dev-1,dev-2,dev-3,qa-1,review-1"
    assert json.loads(labels)["dev-3"] == "开发者"


def test_agent_config_lists_configured_dev_and_pool_agents(tmp_path: Path):
    config_path = tmp_path / "config.json"
    _write_medium_config(config_path)

    dev_ids = subprocess.run(
        [sys.executable, str(AGENT_CONFIG), "list-dev-agent-ids", "--config", str(config_path)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()
    pool_ids = subprocess.run(
        [sys.executable, str(AGENT_CONFIG), "list-pool-agent-ids", "--config", str(config_path)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()

    assert dev_ids == ["dev-1", "dev-2", "dev-3"]
    assert pool_ids == ["arch-1", "dev-1", "dev-2", "dev-3", "qa-1", "review-1"]


def test_send_to_agent_targets_configured_tmux_session(tmp_path: Path):
    config_path = tmp_path / "config.json"
    _write_config(config_path)
    bin_dir, log_path = _fake_tmux(tmp_path)
    env = {
        **os.environ,
        "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}",
        "CONFIG_PATH": str(config_path),
        "SEND_TO_AGENT_INSERT_WAIT_SECONDS": "0",
        "SEND_TO_AGENT_POST_SEND_WAIT_SECONDS": "0",
        "SEND_TO_AGENT_ACK_WAIT_SECONDS": "0",
        "SEND_TO_AGENT_RETRY_LIMIT": "0",
    }

    completed = subprocess.run(
        [str(SEND_TO_AGENT), "dev-1", "hello"],
        cwd=str(REPO_ROOT),
        env=env,
        capture_output=True,
        text=True,
        check=True,
    )

    calls = log_path.read_text(encoding="utf-8")
    assert "delivered to tmux-dev-custom (target=dev-1, runtime=codex" in completed.stdout
    assert "has-session -t tmux-dev-custom" in calls
    assert "send-keys -t tmux-dev-custom" in calls
    assert "has-session -t dev-1" not in calls


def test_task_watcher_session_health_uses_configured_tmux_session(tmp_path: Path):
    config_path = tmp_path / "config.json"
    _write_config(config_path)
    bin_dir, log_path = _fake_tmux(tmp_path)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    (workspace / "config.json").write_text(config_path.read_text(encoding="utf-8"), encoding="utf-8")
    send_script = workspace / "scripts" / "send-to-agent.sh"
    send_script.parent.mkdir()
    send_script.write_text("#!/bin/bash\nexit 0\n", encoding="utf-8")
    send_script.chmod(0o755)
    env = {
        **os.environ,
        "PATH": f"{bin_dir}{os.pathsep}{os.environ.get('PATH', '')}",
        "WORKSPACE_ROOT": str(workspace),
        "CONFIG_PATH": str(config_path),
        "AGENT_CONFIG_PY": str(AGENT_CONFIG),
        "PM_AGENT_ID": "",
        "PM_SESSION": "",
        "TASK_WATCHER_TEST_MODE": "1",
        "STATE_DIR": str(workspace / ".runtime" / "state" / "task-watcher"),
        "LOG_DIR": str(workspace / ".runtime" / "logs"),
        "LOG_FILE": str(workspace / ".runtime" / "logs" / "task-watcher.log"),
        "WATCHER_STDOUT_LOG": str(workspace / ".runtime" / "logs" / "task-watcher.log"),
        "SEND_SCRIPT": str(send_script),
    }
    script = f"""
set -e
source '{TASK_WATCHER}'
test "$(resolve_agent_session dev-1)" = "tmux-dev-custom"
test "$(session_health_state dev-1)" = "working_signal"
"""

    subprocess.run(["bash", "-c", script], cwd=str(REPO_ROOT), env=env, check=True)

    calls = log_path.read_text(encoding="utf-8")
    assert "has-session -t tmux-dev-custom" in calls
    assert "has-session -t dev-1" not in calls


def test_task_watcher_pm_agent_id_uses_configured_root_pm(tmp_path: Path):
    config_path = tmp_path / "config.json"
    _write_custom_pm_config(config_path)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    env = {
        **os.environ,
        "WORKSPACE_ROOT": str(workspace),
        "CONFIG_PATH": str(config_path),
        "AGENT_CONFIG_PY": str(AGENT_CONFIG),
        "TASK_WATCHER_TEST_MODE": "1",
        "STATE_DIR": str(workspace / ".runtime" / "state" / "task-watcher"),
        "LOG_DIR": str(workspace / ".runtime" / "logs"),
        "LOG_FILE": str(workspace / ".runtime" / "logs" / "task-watcher.log"),
        "WATCHER_STDOUT_LOG": str(workspace / ".runtime" / "logs" / "task-watcher.log"),
    }
    script = f"""
set -e
source '{TASK_WATCHER}'
test "$PM_AGENT_ID" = "pm-alt"
test "$(resolve_agent_session "$PM_AGENT_ID")" = "tmux-pm-custom"
"""

    subprocess.run(["bash", "-c", script], cwd=str(REPO_ROOT), env=env, check=True)


def test_task_watcher_role_helpers_use_configured_agent_ids(tmp_path: Path):
    config_path = tmp_path / "config.json"
    _write_custom_role_defaults_config(config_path)
    workspace = tmp_path / "workspace"
    task_dir = tmp_path / "tasks" / "custom-role-task"
    workspace.mkdir()
    task_dir.mkdir(parents=True)
    (task_dir / "task.json").write_text(
        json.dumps(
            {
                "id": "custom-role-task",
                "domain": "development",
                "review_level": "complex",
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    env = {
        **os.environ,
        "WORKSPACE_ROOT": str(workspace),
        "CONFIG_PATH": str(config_path),
        "AGENT_CONFIG_PY": str(AGENT_CONFIG),
        "TASK_WATCHER_TEST_MODE": "1",
        "STATE_DIR": str(workspace / ".runtime" / "state" / "task-watcher"),
        "LOG_DIR": str(workspace / ".runtime" / "logs"),
        "LOG_FILE": str(workspace / ".runtime" / "logs" / "task-watcher.log"),
        "WATCHER_STDOUT_LOG": str(workspace / ".runtime" / "logs" / "task-watcher.log"),
    }
    script = f"""
set -e
source '{TASK_WATCHER}'
test "$PM_AGENT_ID" = "lead-pm"
test "$INTEGRATION_OWNER_AGENT_ID" = "principal-architect"
test "$(list_qa_agents)" = "release-qa"
test "$(default_tester_agent '{task_dir}')" = "release-qa"
test "$(task_reviewers '{task_dir}')" = $'quality-reviewer\\nprincipal-architect'
is_integration_owner_planning_task principal-architect domain
! is_integration_owner_planning_task arch-1 domain
"""

    subprocess.run(["bash", "-c", script], cwd=str(REPO_ROOT), env=env, check=True)


def test_send_chat_infers_agent_from_configured_workdir_subdirectory(tmp_path: Path):
    workspace = tmp_path / "workspace"
    agent_src = workspace / "agents" / "dev-1" / "src"
    agent_src.mkdir(parents=True)
    chat_root = workspace / "chat"
    config_path = workspace / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "orchestration": {"root_pm": "pm-chief"},
                "agents": {
                    "pm-chief": {"role": "pm", "workdir": "agents/pm-chief"},
                    "dev-1": {"role": "fullstack_dev", "workdir": "agents/dev-1"},
                },
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    subprocess.run(
        [str(SEND_CHAT), "general", "hello from src"],
        cwd=str(agent_src),
        env={
            **os.environ,
            "WORKSPACE_ROOT": str(workspace),
            "CHAT_ROOT": str(chat_root),
            "CONFIG_PATH": str(config_path),
            "AGENT_CONFIG_PY": str(AGENT_CONFIG),
        },
        capture_output=True,
        text=True,
        check=True,
    )

    messages = [
        json.loads(line)
        for line in next((chat_root / "general").glob("*.jsonl")).read_text(encoding="utf-8").splitlines()
    ]
    assert messages[-1]["from"] == "dev-1"


def test_task_watcher_auto_claims_configured_dev_agent_without_dev_prefix(tmp_path: Path):
    config_path = tmp_path / "config.json"
    _write_custom_role_defaults_config(config_path)
    workspace = tmp_path / "workspace"
    task_dir = tmp_path / "tasks" / "custom-dev-task"
    delivery_log = tmp_path / "delivery.log"
    workspace.mkdir()
    task_dir.mkdir(parents=True)
    (task_dir / "task.json").write_text(
        json.dumps(
            {
                "id": "custom-dev-task",
                "title": "自定义开发者任务",
                "status": "pending",
                "assigned_agent": "builder-a",
                "task_level": "execution",
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    (task_dir / "transitions.jsonl").write_text("", encoding="utf-8")
    env = {
        **os.environ,
        "WORKSPACE_ROOT": str(workspace),
        "CONFIG_PATH": str(config_path),
        "AGENT_CONFIG_PY": str(AGENT_CONFIG),
        "TASK_WATCHER_TEST_MODE": "1",
        "STATE_DIR": str(workspace / ".runtime" / "state" / "task-watcher"),
        "LOG_DIR": str(workspace / ".runtime" / "logs"),
        "LOG_FILE": str(workspace / ".runtime" / "logs" / "task-watcher.log"),
        "WATCHER_STDOUT_LOG": str(workspace / ".runtime" / "logs" / "task-watcher.log"),
        "DELIVERY_LOG": str(delivery_log),
    }
    script = f"""
set -e
source '{TASK_WATCHER}'
dependencies_ready() {{ return 0; }}
is_idle_agent() {{ [ "$1" = "builder-a" ]; }}
prepare_task_workspace_payload() {{ printf '{{}}'; }}
workspace_hint_from_payload() {{ return 0; }}
sync_task_board() {{ return 0; }}
deliver_execution_instruction_and_record() {{
  printf '%s\\t%s\\t%s\\t%s\\n' "$1" "$2" "$3" "$4" >> "$DELIVERY_LOG"
}}
auto_claim_pending_dev '{task_dir}' 'custom-dev-task' 'builder-a' 'execution'
python3 - <<'PY'
import json
from pathlib import Path
task_dir = Path(r'{task_dir}')
task = json.loads((task_dir / 'task.json').read_text(encoding='utf-8'))
assert task['status'] == 'dispatched', task
assert task['assigned_agent'] == 'builder-a', task
delivery = Path(r'{delivery_log}').read_text(encoding='utf-8')
assert str(task_dir / 'instruction.md') in delivery, delivery
assert '/Users/linsuchang/Desktop/work/my-agent-teams/tasks/custom-dev-task/instruction.md' not in delivery, delivery
PY
"""

    subprocess.run(["bash", "-c", script], cwd=str(REPO_ROOT), env=env, check=True)


def test_task_state_invariants_design_claim_scope_uses_configured_architect(tmp_path: Path):
    config_path = tmp_path / "config.json"
    _write_custom_role_defaults_config(config_path)
    task_dir = tmp_path / "tasks" / "design-task"
    task_dir.mkdir(parents=True)
    (task_dir / "task.json").write_text(
        json.dumps(
            {
                "id": "design-task",
                "status": "pooled",
                "claim_policy": "pull",
                "assigned_agent": "principal-architect",
                "task_type": "design",
                "review_required": True,
                "test_required": False,
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )

    completed = subprocess.run(
        [sys.executable, str(TASK_STATE_INVARIANTS), "--task-dir", str(task_dir), "--config", str(config_path)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=True,
    )

    payload = json.loads(completed.stdout)
    assert payload["count"] == 0
    assert payload["violations"] == []


def test_task_watcher_pm_session_env_keeps_legacy_override(tmp_path: Path):
    config_path = tmp_path / "config.json"
    _write_custom_pm_config(config_path)
    workspace = tmp_path / "workspace"
    workspace.mkdir()
    env = {
        **os.environ,
        "WORKSPACE_ROOT": str(workspace),
        "CONFIG_PATH": str(config_path),
        "AGENT_CONFIG_PY": str(AGENT_CONFIG),
        "PM_AGENT_ID": "",
        "PM_SESSION": "legacy-pm",
        "TASK_WATCHER_TEST_MODE": "1",
        "STATE_DIR": str(workspace / ".runtime" / "state" / "task-watcher"),
        "LOG_DIR": str(workspace / ".runtime" / "logs"),
        "LOG_FILE": str(workspace / ".runtime" / "logs" / "task-watcher.log"),
        "WATCHER_STDOUT_LOG": str(workspace / ".runtime" / "logs" / "task-watcher.log"),
    }
    script = f"""
set -e
source '{TASK_WATCHER}'
test "$PM_AGENT_ID" = "legacy-pm"
"""

    subprocess.run(["bash", "-c", script], cwd=str(REPO_ROOT), env=env, check=True)


def test_generated_report_uses_configured_agent_list(tmp_path: Path):
    config_path = tmp_path / "config.json"
    _write_medium_config(config_path)
    data_path = tmp_path / "gantt.json"
    out_path = tmp_path / "report.md"
    data_path.write_text(
        json.dumps(
            {
                "items": [
                    {
                        "assigned_agent": "dev-3",
                        "board_status": "done",
                        "title": "中团队新增开发任务",
                        "display_end_at": "2026-05-25T10:00:00+08:00",
                    },
                    {
                        "assigned_agent": "dev-1",
                        "board_status": "blocked",
                        "title": "已有开发任务",
                    },
                    {
                        "assigned_agent": "outsider",
                        "board_status": "done",
                        "title": "不属于当前团队",
                    },
                ]
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )
    env = {**os.environ, "CONFIG_PATH": str(config_path)}

    subprocess.run(
        [
            sys.executable,
            str(GEN_REPORT),
            "daily",
            "日报",
            "2026-05-25",
            "2026-05-25",
            "2026-05-25 12:00:00 CST",
            str(out_path),
            str(data_path),
        ],
        cwd=str(REPO_ROOT),
        env=env,
        check=True,
    )

    report = out_path.read_text(encoding="utf-8")
    assert "- 总任务数：2" in report
    assert "- 已完成：1（50.0%）" in report
    assert "| dev-3(开发者) | 1 | 1 | 0 | 0 | 0% |" in report
    assert "不属于当前团队" not in report


def _write_task_dir(task_dir: Path, payload: dict, *, instruction: bool = False) -> None:
    task_dir.mkdir(parents=True, exist_ok=True)
    (task_dir / "task.json").write_text(
        json.dumps(payload, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (task_dir / "transitions.jsonl").write_text("", encoding="utf-8")
    if instruction:
        (task_dir / "instruction.md").write_text(
            "\n".join(
                [
                    f"# 任务：{payload.get('title') or payload.get('id')}",
                    "## 任务类型",
                    str(payload.get("task_type") or "development"),
                    "## 目标",
                    "完成任务",
                    "## 任务边界",
                    "按 scope 执行",
                    "## 输入事实",
                    "已有上下文",
                    "## 约束",
                    "遵守 write_scope",
                    "## 交付物",
                    "result.json",
                    "## 验收标准",
                    "任务完成",
                    "## 下游动作",
                    "review",
                ]
            )
            + "\n",
            encoding="utf-8",
        )


def test_task_state_scripts_use_configured_root_pm(tmp_path: Path):
    config_path = tmp_path / "config.json"
    _write_custom_pm_config(config_path)
    tasks_root = tmp_path / "tasks"

    resume_dir = tasks_root / "resume-task"
    _write_task_dir(
        resume_dir,
        {
            "id": "resume-task",
            "title": "恢复任务",
            "status": "blocked",
            "assigned_agent": "dev-1",
        },
    )
    subprocess.run(
        [str(RESUME_TASK), "--task-dir", str(resume_dir), "--agent", "dev-1", "--reason", "retry"],
        cwd=str(REPO_ROOT),
        env={**os.environ, "CONFIG_PATH": str(config_path), "STATE_DIR": str(tmp_path / "state")},
        capture_output=True,
        text=True,
        check=True,
    )
    resume_payload = json.loads((resume_dir / "task.json").read_text(encoding="utf-8"))
    resume_record = next((resume_dir / "history").glob("resume.*.json"))
    resume_transition = json.loads((resume_dir / "transitions.jsonl").read_text(encoding="utf-8").splitlines()[-1])
    assert resume_payload["last_gate_actor"] == "pm-alt"
    assert resume_payload["last_resumed_by"] == "pm-alt"
    assert resume_payload["lease_owner"] == "pm-alt"
    assert json.loads(resume_record.read_text(encoding="utf-8"))["resumed_by"] == "pm-alt"
    assert resume_transition["actor"] == "pm-alt"

    reassign_dir = tasks_root / "reassign-task"
    _write_task_dir(
        reassign_dir,
        {
            "id": "reassign-task",
            "title": "重派任务",
            "status": "dispatched",
            "assigned_agent": "dev-1",
        },
    )
    subprocess.run(
        [str(REASSIGN_TASK), "--task-dir", str(reassign_dir), "--agent", "dev-2", "--reason", "session unhealthy"],
        cwd=str(REPO_ROOT),
        env={**os.environ, "CONFIG_PATH": str(config_path), "STATE_DIR": str(tmp_path / "state")},
        capture_output=True,
        text=True,
        check=True,
    )
    reassign_payload = json.loads((reassign_dir / "task.json").read_text(encoding="utf-8"))
    assert reassign_payload["lease_owner"] == "pm-alt"

    close_dir = tasks_root / "close-task"
    _write_task_dir(
        close_dir,
        {
            "id": "close-task",
            "title": "关闭任务",
            "status": "ready_for_merge",
            "task_type": "development",
            "review_required": False,
            "test_required": False,
            "merge_gate_state": "",
            "result_summary": "finished",
        },
    )
    (close_dir / "result.json").write_text(
        json.dumps({"task_id": "close-task", "agent": "dev-1", "status": "success", "summary": "done"}) + "\n",
        encoding="utf-8",
    )
    subprocess.run(
        [str(CLOSE_TASK), "--task-dir", str(close_dir), "--summary", "finished", "--reason", "manual close"],
        cwd=str(REPO_ROOT),
        env={**os.environ, "CONFIG_PATH": str(config_path)},
        capture_output=True,
        text=True,
        check=True,
    )
    close_payload = json.loads((close_dir / "task.json").read_text(encoding="utf-8"))
    assert close_payload["last_gate_actor"] == "pm-alt"


def test_pool_and_chat_scripts_use_configured_root_pm(tmp_path: Path):
    config_path = tmp_path / "config.json"
    _write_custom_pm_config(config_path)
    task_dir = tmp_path / "tasks" / "pooled-task"
    _write_task_dir(
        task_dir,
        {
            "id": "pooled-task",
            "title": "入池任务",
            "status": "pending",
            "assigned_agent": "auto",
            "project": "demo",
            "task_type": "development",
            "domain": "development",
            "execution_mode": "dev",
            "target_environment": "dev",
            "task_level": "execution",
            "priority": "medium",
            "write_scope": ["src/a.txt"],
            "claim_scope": ["dev-1"],
        },
        instruction=True,
    )
    send_chat = tmp_path / "send-chat-stub.sh"
    send_log = tmp_path / "send-chat-env.log"
    send_chat.write_text(
        "#!/bin/bash\n"
        f"printf '%s\\n' \"$CHAT_FROM\" > '{send_log}'\n"
        "exit 0\n",
        encoding="utf-8",
    )
    send_chat.chmod(0o755)

    subprocess.run(
        [str(POOL_TASK), str(task_dir / "task.json")],
        cwd=str(REPO_ROOT),
        env={
            **os.environ,
            "WORKSPACE_ROOT": str(REPO_ROOT),
            "CONFIG_PATH": str(config_path),
            "SEND_CHAT_SCRIPT": str(send_chat),
            "SEND_SCRIPT": str(tmp_path / "missing-send.sh"),
        },
        capture_output=True,
        text=True,
        check=True,
    )
    assert send_log.read_text(encoding="utf-8").strip() == "pm-alt"

    chat_root = tmp_path / "chat"
    subprocess.run(
        [str(SEND_CHAT), "general", "hello"],
        cwd=str(tmp_path),
        env={
            **os.environ,
            "WORKSPACE_ROOT": str(REPO_ROOT),
            "CONFIG_PATH": str(config_path),
            "CHAT_ROOT": str(chat_root),
        },
        capture_output=True,
        text=True,
        check=True,
    )
    chat_rows = [
        json.loads(line)
        for line in next((chat_root / "general").glob("*.jsonl")).read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    assert chat_rows[-1]["from"] == "pm-alt"


def test_chat_pm_detection_uses_configured_root_pm(tmp_path: Path):
    config_path = tmp_path / "config.json"
    _write_custom_pm_config(config_path)
    chat_root = tmp_path / "chat"
    general = chat_root / "general"
    general.mkdir(parents=True)
    (general / "2026-05-25.jsonl").write_text(
        json.dumps(
            {
                "msg_id": "m1",
                "ts": "2099-01-01T00:00:00+08:00",
                "from": "dev-1",
                "to": "pm-alt",
                "source_type": "human",
                "type": "text",
                "msg": "@pm-alt 请看一下",
                "schema_version": 1,
            },
            ensure_ascii=False,
        )
        + "\n",
        encoding="utf-8",
    )

    metrics = subprocess.run(
        [sys.executable, str(CHAT_METRICS), "--chat-root", str(chat_root), "--config", str(config_path), "--days", "36500", "--json"],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=True,
    )
    assert json.loads(metrics.stdout)["summary"]["pm_mention_count"] == 1

    check = subprocess.run(
        [str(PM_CHAT_CHECK), "--days", "36500", "--no-metrics"],
        cwd=str(REPO_ROOT),
        env={**os.environ, "CHAT_ROOT": str(chat_root), "CONFIG_PATH": str(config_path)},
        capture_output=True,
        text=True,
        check=True,
    )
    assert "actionable=1" in check.stdout


def test_pm_capacity_uses_role_key_and_configured_root_pm(tmp_path: Path):
    config_path = tmp_path / "config.json"
    config_path.write_text(
        json.dumps(
            {
                "orchestration": {"root_pm": "lead-pm"},
                "agents": {"lead-pm": {"role": "pm"}},
                "task_pool": {"default_working_limit": 5, "default_reserved_limit": 1},
                "wip_limits": {"pm": 2},
            },
            ensure_ascii=False,
            indent=2,
        )
        + "\n",
        encoding="utf-8",
    )
    tasks_root = tmp_path / "tasks"
    tasks_root.mkdir()

    completed = subprocess.run(
        ["bash", str(AGENT_AVAILABILITY), "json", "lead-pm", str(tasks_root), str(config_path)],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=True,
    )
    payload = json.loads(completed.stdout)
    assert payload["capacity"]["working_limit"] == 2
