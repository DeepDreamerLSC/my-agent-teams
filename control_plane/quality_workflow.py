from __future__ import annotations

from typing import Any, Mapping

from .errors import ControlPlaneError, GateConflict
from .quality_governance import (
    delivery_summary_contract_error,
    quality_report_contract_error,
    review_pass_contract_error,
    review_rejection_contract_error,
    summarize_quality_report,
)
from .workflow import STAGE_BY_NAME


def validate_artifact_metadata(
    kind: str, metadata: Mapping[str, Any] | None
) -> dict[str, Any]:
    payload = dict(metadata or {})
    if kind != "quality_report":
        return payload
    contract_error = quality_report_contract_error(payload)
    if contract_error:
        raise ControlPlaneError(contract_error, code="invalid_quality_report")
    return payload


def validate_gate_contract(
    stage: str,
    status: str,
    output: Mapping[str, Any] | None,
    rejection_reason: str | None,
) -> None:
    contract_error = review_rejection_contract_error(stage, status, output, rejection_reason)
    if contract_error:
        raise GateConflict(contract_error)


def validate_passing_quality_gate(
    service: Any,
    requirement: Mapping[str, Any],
    stage: str,
    output: Mapping[str, Any],
) -> None:
    if stage in {"quality_gate", "review"}:
        quality = quality_summary_for_requirement(service, requirement)
        if not quality["passed"]:
            raise GateConflict("quality report is not passable: " + str(quality["reason"]))
    if stage == "review":
        review_error = review_pass_contract_error(output)
        if review_error:
            raise GateConflict(review_error)
    if stage == "delivery_summary":
        delivery_error = delivery_summary_error(service, requirement)
        if delivery_error:
            raise GateConflict(delivery_error)


def gate_rejection_target(stage: str, definition: Mapping[str, Any]) -> str:
    reject_target = str(definition.get("reject_to") or "")
    return reject_target if reject_target in STAGE_BY_NAME else stage


def advance_quality_workflow_stage(
    service: Any,
    requirement: Mapping[str, Any],
    stage: str,
    *,
    actor: str,
    task_id: str | None,
) -> dict[str, Any] | None:
    if stage == "quality_gate":
        return _advance_quality_gate(service, requirement, actor=actor, task_id=task_id)
    quality = quality_summary_for_requirement(service, requirement) if stage == "review" else None
    delivery_error = delivery_summary_error(service, requirement) if stage == "delivery_summary" else None
    return _workflow_quality_guard(
        stage,
        requirement,
        quality=quality,
        delivery_error=delivery_error,
    )


def current_stage_artifacts(
    conn: Any,
    requirement: Mapping[str, Any],
    stage: str,
    artifacts: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    stage_order = list(STAGE_BY_NAME)
    if stage not in stage_order or stage_order.index(stage) < stage_order.index("development"):
        return artifacts
    row = conn.execute(
        "SELECT decided_at FROM control_plane_gates "
        "WHERE requirement_id = ? AND stage IN ('quality_gate', 'review', 'qa') "
        "AND status = 'rejected' ORDER BY decided_at DESC, rowid DESC LIMIT 1",
        (str(requirement["requirement_id"]),),
    ).fetchone()
    cutoff = str(row["decided_at"]) if row and row["decided_at"] else None
    if not cutoff:
        return artifacts
    return [item for item in artifacts if str(item.get("created_at") or "") > cutoff]


def summarize_requirement_quality(
    conn: Any,
    requirements: list[dict[str, Any]],
    artifacts: list[dict[str, Any]],
) -> dict[str, dict[str, Any]]:
    quality_artifacts: dict[str, list[dict[str, Any]]] = {}
    for artifact in artifacts:
        requirement_id = artifact.get("requirement_id")
        if requirement_id and artifact.get("kind") == "quality_report":
            quality_artifacts.setdefault(str(requirement_id), []).append(artifact)
    summaries: dict[str, dict[str, Any]] = {}
    for requirement in requirements:
        requirement_id = str(requirement["requirement_id"])
        candidates = quality_artifacts.get(requirement_id)
        if not candidates:
            continue
        stage = str(requirement.get("current_stage") or "quality_gate")
        current = current_stage_artifacts(conn, requirement, stage, candidates)
        summaries[requirement_id] = summarize_quality_report(_latest_artifact(current, "quality_report"))
    return summaries


def quality_summary_for_requirement(
    service: Any, requirement: Mapping[str, Any]
) -> dict[str, Any]:
    stage = str(requirement.get("current_stage") or "quality_gate")
    artifact = _current_artifact(service, requirement, "quality_report", stage=stage)
    return summarize_quality_report(artifact)


def delivery_summary_error(service: Any, requirement: Mapping[str, Any]) -> str | None:
    artifact = _current_artifact(
        service, requirement, "delivery_summary", stage="delivery_summary"
    )
    return delivery_summary_contract_error(artifact)


def _advance_quality_gate(
    service: Any,
    requirement: Mapping[str, Any],
    *,
    actor: str,
    task_id: str | None,
) -> dict[str, Any]:
    quality = quality_summary_for_requirement(service, requirement)
    if quality["passed"]:
        result = service.decide_gate(
            requirement_id=str(requirement["requirement_id"]),
            stage="quality_gate",
            status="passed",
            actor=actor,
            output={"verdict": "pass", "quality": quality},
            task_id=task_id,
        )
        return {"advanced": True, "quality": quality, **result}
    infrastructure_failure = quality["failure_category"] == "infrastructure_failure"
    result = service.decide_gate(
        requirement_id=str(requirement["requirement_id"]),
        stage="quality_gate",
        status="blocked" if infrastructure_failure else "rejected",
        actor=actor,
        output={"verdict": "block", "quality": quality, "findings": quality["findings"]},
        rejection_reason=str(quality["reason"]),
        task_id=task_id,
    )
    return {
        "advanced": False,
        "reason": (
            "quality_gate_infrastructure_failure"
            if infrastructure_failure
            else "quality_gate_rejected"
        ),
        "quality": quality,
        **result,
    }


def _workflow_quality_guard(
    stage: str,
    requirement: Mapping[str, Any],
    *,
    quality: Mapping[str, Any] | None,
    delivery_error: str | None,
) -> dict[str, Any] | None:
    if stage == "review" and quality is not None and not quality["passed"]:
        return {
            "advanced": False,
            "reason": "quality_report_not_passable",
            "quality": quality,
            "requirement": requirement,
        }
    if stage == "delivery_summary" and delivery_error:
        return {
            "advanced": False,
            "reason": "delivery_quality_summary_incomplete",
            "message": delivery_error,
            "requirement": requirement,
        }
    return None


def _current_artifact(
    service: Any,
    requirement: Mapping[str, Any],
    kind: str,
    *,
    stage: str,
) -> dict[str, Any] | None:
    artifacts = service.list_artifacts(
        project_id=str(requirement["project_id"]),
        requirement_id=str(requirement["requirement_id"]),
    )
    current = current_stage_artifacts(service.conn, requirement, stage, artifacts)
    return _latest_artifact(current, kind)


def _latest_artifact(artifacts: list[dict[str, Any]], kind: str) -> dict[str, Any] | None:
    return next((item for item in artifacts if str(item.get("kind")) == kind), None)
