from __future__ import annotations

from typing import Any

STAGES: tuple[dict[str, Any], ...] = (
    {
        "name": "pm_clarification",
        "role": "pm",
        "entry": "Owner has submitted a goal.",
        "outputs": ("clarified requirement", "acceptance criteria"),
        "reject_to": "same_stage_rework",
        "next": "architecture",
    },
    {
        "name": "architecture",
        "role": "architect",
        "entry": "PM clarification and acceptance criteria are present.",
        "outputs": ("architecture decision", "risk list"),
        "artifact_kinds": ("architecture",),
        "reject_to": "same_stage_rework_or_owner",
        "next": "critic_review",
    },
    {
        "name": "critic_review",
        "role": "critic",
        "entry": "Architecture output exists and critic has independent context.",
        "outputs": ("independent critic report",),
        "artifact_kinds": ("critic_review",),
        "reject_to": "same_stage_rework_or_owner",
        "next": "task_decomposition",
    },
    {
        "name": "task_decomposition",
        "role": "pm",
        "entry": "Architecture and critic review passed.",
        "outputs": ("tasks", "dependencies", "acceptance mapping"),
        "artifact_kinds": ("task_plan",),
        "reject_to": "same_stage_rework",
        "next": "development",
    },
    {
        "name": "development",
        "role": "developer",
        "entry": "Task decomposition passed and a project worktree is assigned.",
        "outputs": ("branch", "implementation evidence", "tests"),
        "artifact_kinds": ("implementation", "test_evidence"),
        "reject_to": "same_stage_rework",
        "next": "review",
    },
    {
        "name": "review",
        "role": "reviewer",
        "entry": "Developer evidence and diff reference are available.",
        "outputs": ("independent review verdict", "findings"),
        "artifact_kinds": ("review",),
        "reject_to": "same_stage_rework_or_owner",
        "next": "qa",
    },
    {
        "name": "qa",
        "role": "qa",
        "entry": "Review passed and test evidence is available.",
        "outputs": ("test results", "acceptance verdict"),
        "artifact_kinds": ("qa",),
        "reject_to": "same_stage_rework_or_owner",
        "next": "delivery_summary",
    },
    {
        "name": "delivery_summary",
        "role": "pm",
        "entry": "QA passed and required delivery evidence is attached.",
        "outputs": ("delivery summary", "residual risks"),
        "artifact_kinds": ("delivery_summary",),
        "reject_to": "same_stage_rework",
        "next": "release_ready",
    },
    {
        "name": "release_ready",
        "role": "pm",
        "entry": "PM summary is complete; no Owner exception remains open.",
        "outputs": ("release readiness decision",),
        "next": None,
        "reject_to": "owner_decision",
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
EXPLICIT_VERDICT_STAGES = {"architecture", "critic_review", "review", "qa"}
INDEPENDENT_REVIEW_ROLES = {
    "critic_review": ("architect",),
    "review": ("developer",),
    "qa": ("developer", "reviewer"),
}


def stage_definition(stage: str) -> dict[str, Any]:
    try:
        return STAGE_BY_NAME[stage]
    except KeyError as exc:
        raise ValueError(f"unknown workflow stage: {stage}") from exc


def stage_names() -> list[str]:
    return [stage["name"] for stage in STAGES]
