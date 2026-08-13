from __future__ import annotations

from typing import Any

STAGES: tuple[dict[str, Any], ...] = (
    {
        "name": "pm_clarification",
        "role": "pm",
        "entry": "Owner has submitted a goal.",
        "outputs": ("clarified requirement", "acceptance criteria"),
        "next": "architecture",
    },
    {
        "name": "architecture",
        "role": "architect",
        "entry": "PM clarification and acceptance criteria are present.",
        "outputs": ("architecture decision", "risk list"),
        "next": "critic_review",
    },
    {
        "name": "critic_review",
        "role": "critic",
        "entry": "Architecture output exists and critic has independent context.",
        "outputs": ("independent critic report",),
        "next": "task_decomposition",
    },
    {
        "name": "task_decomposition",
        "role": "pm",
        "entry": "Architecture and critic review passed.",
        "outputs": ("tasks", "dependencies", "acceptance mapping"),
        "next": "development",
    },
    {
        "name": "development",
        "role": "developer",
        "entry": "Task decomposition passed and a project worktree is assigned.",
        "outputs": ("branch", "implementation evidence", "tests"),
        "next": "review",
    },
    {
        "name": "review",
        "role": "reviewer",
        "entry": "Developer evidence and diff reference are available.",
        "outputs": ("independent review verdict", "findings"),
        "next": "qa",
    },
    {
        "name": "qa",
        "role": "qa",
        "entry": "Review passed and test evidence is available.",
        "outputs": ("test results", "acceptance verdict"),
        "next": "delivery_summary",
    },
    {
        "name": "delivery_summary",
        "role": "pm",
        "entry": "QA passed and required delivery evidence is attached.",
        "outputs": ("delivery summary", "residual risks"),
        "next": "release_ready",
    },
    {
        "name": "release_ready",
        "role": "pm",
        "entry": "PM summary is complete; no Owner exception remains open.",
        "outputs": ("release readiness decision",),
        "next": None,
    },
)

STAGE_BY_NAME = {stage["name"]: stage for stage in STAGES}
OWNER_DECISION_CATEGORIES = {
    "scope_conflict",
    "resource_conflict",
    "irreversible_architecture",
    "production_release",
    "credentials",
    "security_compliance",
    "repeated_gate_failure",
    "external_payment",
}


def stage_definition(stage: str) -> dict[str, Any]:
    try:
        return STAGE_BY_NAME[stage]
    except KeyError as exc:
        raise ValueError(f"unknown workflow stage: {stage}") from exc


def stage_names() -> list[str]:
    return [stage["name"] for stage in STAGES]
