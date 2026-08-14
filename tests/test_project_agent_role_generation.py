from __future__ import annotations

import json
import os
import subprocess
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]
BUILD_SCRIPT = REPO_ROOT / "scripts" / "build-agent-files.sh"
ROLE_TEMPLATE_PATHS = [
    REPO_ROOT / "design" / "agent-templates" / "base.md",
    REPO_ROOT / "design" / "agent-templates" / "pm.md",
    REPO_ROOT / "design" / "agent-templates" / "architect.md",
    REPO_ROOT / "design" / "agent-templates" / "developer.md",
    REPO_ROOT / "design" / "agent-templates" / "critic.md",
    REPO_ROOT / "design" / "agent-templates" / "reviewer.md",
    REPO_ROOT / "design" / "agent-templates" / "qa.md",
]
FORBIDDEN_CORE_TERMS = [
    "pm-chief",
    "arch-1",
    "dev-1",
    "dev-2",
    "review-1",
    "qa-1",
    "/Users/linsuchang",
    "tmux",
    "A-Lite",
    "飞书",
    "codex_app",
]


def run_build(config: dict, agents_root: Path) -> subprocess.CompletedProcess[str]:
    agents_root.mkdir(parents=True, exist_ok=True)
    config_path = agents_root / "config.json"
    config_path.write_text(json.dumps(config), encoding="utf-8")
    env = {
        **os.environ,
        "WORKSPACE_ROOT": str(REPO_ROOT),
        "CONFIG_PATH": str(config_path),
        "AGENTS_DIR": str(agents_root),
    }
    return subprocess.run(
        [str(BUILD_SCRIPT)],
        check=True,
        env=env,
        capture_output=True,
        text=True,
    )


def test_project_agents_generate_overlay_and_role_composition(tmp_path: Path) -> None:
    agents_root = tmp_path / "agents"
    run_build(
        {
            "agents": {
                "legacy-dev": {"role": "fullstack_dev", "runtime": "codex"},
                "legacy-review": {"role": "reviewer", "runtime": "claude_code"},
            },
            "project_agents": {
                "edu-agent": {
                    "edu-pm-1": {
                        "role": "pm",
                        "runtime": "codex",
                        "execution_surface": "codex_app",
                    },
                    "edu-critic-1": {
                        "role": "critic",
                        "runtime": "codex",
                        "execution_surface": "codex_app",
                    },
                    "edu-qa-software-1": {
                        "role": "software_qa",
                        "runtime": "codex",
                        "execution_surface": "codex_app",
                    },
                    "edu-qa-education-1": {
                        "role": "education_qa",
                        "runtime": "codex",
                        "execution_surface": "codex_app",
                    },
                }
            },
        },
        agents_root,
    )

    codex_app_agent = (agents_root / "edu-pm-1" / "AGENT.md").read_text(encoding="utf-8")
    critic = (agents_root / "edu-critic-1" / "AGENT.md").read_text(encoding="utf-8")
    software_qa = (agents_root / "edu-qa-software-1" / "AGENT.md").read_text(encoding="utf-8")
    education_qa = (agents_root / "edu-qa-education-1" / "AGENT.md").read_text(encoding="utf-8")
    legacy_dev = (agents_root / "legacy-dev" / "AGENT.md").read_text(encoding="utf-8")
    legacy_review = (agents_root / "legacy-review" / "AGENT.md").read_text(encoding="utf-8")

    assert "Overlay 来源: design/agent-templates/overlays/codex_app.md" in codex_app_agent
    assert "tmux 指令" not in codex_app_agent
    assert "长期项目绑定：`edu-agent`" in codex_app_agent

    assert "design/agent-templates/critic.md" in critic
    assert "过度设计" in critic

    assert "design/agent-templates/qa.md" in software_qa
    assert "design/agent-templates/software-qa.md" in software_qa
    assert "blocked_by_infrastructure" in software_qa

    assert "design/agent-templates/qa.md" in education_qa
    assert "design/agent-templates/education-qa.md" in education_qa
    assert "active_subquestion_index" in education_qa

    assert "Overlay 来源: design/agent-templates/overlays/tmux.md" in legacy_dev
    assert "Overlay 来源: design/agent-templates/overlays/tmux.md" in legacy_review


def test_generated_agent_and_claude_files_are_identical(tmp_path: Path) -> None:
    agents_root = tmp_path / "agents"
    run_build(
        {"agents": {"dev-a": {"role": "developer", "runtime": "codex"}}},
        agents_root,
    )

    agent_text = (agents_root / "dev-a" / "AGENT.md").read_text(encoding="utf-8")
    claude_text = (agents_root / "dev-a" / "CLAUDE.md").read_text(encoding="utf-8")

    assert agent_text == claude_text


def test_unknown_execution_surface_fails_closed(tmp_path: Path) -> None:
    config_path = tmp_path / "config.json"
    agents_root = tmp_path / "agents"
    config_path.write_text(
        json.dumps(
            {
                "project_agents": {
                    "edu-agent": {
                        "edu-dev-1": {
                            "role": "developer",
                            "runtime": "codex",
                            "execution_surface": "mystery_surface",
                        }
                    }
                }
            }
        ),
        encoding="utf-8",
    )
    env = {
        **os.environ,
        "WORKSPACE_ROOT": str(REPO_ROOT),
        "CONFIG_PATH": str(config_path),
        "AGENTS_DIR": str(agents_root),
    }

    result = subprocess.run(
        [str(BUILD_SCRIPT)],
        check=False,
        env=env,
        capture_output=True,
        text=True,
    )

    assert result.returncode != 0
    assert "Unsupported execution_surface 'mystery_surface'" in result.stderr


def test_core_templates_exclude_legacy_ids_paths_and_runtime_terms() -> None:
    for path in ROLE_TEMPLATE_PATHS:
        text = path.read_text(encoding="utf-8")
        for term in FORBIDDEN_CORE_TERMS:
            assert term not in text, f"{term!r} leaked into {path}"


def test_quality_evidence_contract_present_for_core_roles() -> None:
    expected = {
        "pm.md": "质量与证据契约",
        "architect.md": "质量与证据契约",
        "developer.md": "quality_report",
        "critic.md": "质量与证据契约",
        "reviewer.md": "质量与证据契约",
        "qa.md": "质量与证据契约",
    }

    template_dir = REPO_ROOT / "design" / "agent-templates"
    for filename, marker in expected.items():
        text = (template_dir / filename).read_text(encoding="utf-8")
        assert marker in text
