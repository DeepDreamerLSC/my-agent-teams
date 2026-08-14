from __future__ import annotations

from typing import Any, Mapping


ALLOWED_RESULT_STATUSES = {"passed", "failed", "timeout", "skipped", "infra_error"}
RESOLVED_FINDING_STATUSES = {"resolved", "accepted", "waived", "closed", "fixed"}


def quality_report_contract_error(metadata: Mapping[str, Any]) -> str | None:
    report = _report_payload(metadata)
    header_error = _report_header_contract_error(report)
    if header_error:
        return header_error
    results = report["results"]
    assert isinstance(results, list)
    for index, result in enumerate(results):
        error = _result_contract_error(result, index)
        if error:
            return error
    return None


def summarize_quality_report(artifact: Mapping[str, Any] | None) -> dict[str, Any]:
    if artifact is None:
        return _empty_summary("a current quality_report artifact is required")
    metadata = artifact.get("metadata")
    if not isinstance(metadata, Mapping):
        metadata = {}
    contract_error = quality_report_contract_error(metadata)
    if contract_error:
        return _empty_summary(contract_error, artifact_id=artifact.get("artifact_id"))

    report = _report_payload(metadata)
    results = [item for item in report.get("results", []) if isinstance(item, Mapping)]
    blocking_results = _blocking_results(results)
    infrastructure_results = [
        item for item in blocking_results if str(item.get("status")) in {"timeout", "infra_error"}
    ]
    evidence = _collect_evidence(results, report)
    failure_category, reason = _failure_reason(
        report,
        blocking_results,
        infrastructure_results,
        evidence,
    )
    return {
        "passed": failure_category is None,
        "failure_category": failure_category,
        "reason": reason,
        "artifact_id": artifact.get("artifact_id"),
        "schema_version": report.get("schema_version"),
        "scenario": report.get("scenario"),
        "blocking_results": blocking_results,
        **evidence,
    }


def review_rejection_contract_error(
    stage: str,
    status: str,
    output: Mapping[str, Any] | None,
    rejection_reason: str | None,
) -> str | None:
    if stage != "review" or status != "rejected":
        return None
    if not rejection_reason:
        return "a rejected review requires a rejection reason"
    if not isinstance(output, Mapping) or not isinstance(output.get("findings"), list):
        return "a rejected review requires structured findings"
    return None


def review_pass_contract_error(output: Mapping[str, Any]) -> str | None:
    findings = output.get("findings")
    if not isinstance(findings, list):
        return "a review pass requires a structured findings list"
    unresolved = [finding for finding in findings if _review_finding_is_unresolved(finding)]
    if unresolved:
        return f"review has {len(unresolved)} unresolved blocking findings"
    return None


def delivery_summary_contract_error(artifact: Mapping[str, Any] | None) -> str | None:
    if artifact is None:
        return "delivery_summary artifact is required"
    metadata = artifact.get("metadata")
    quality_summary = metadata.get("quality_summary") if isinstance(metadata, Mapping) else None
    if not isinstance(quality_summary, Mapping):
        return "delivery_summary metadata requires quality_summary"
    required = {"debt_added", "debt_reduced", "active_waivers", "residual_risks"}
    missing = sorted(required - set(quality_summary))
    if missing:
        return "delivery quality_summary is missing: " + ", ".join(missing)
    if not isinstance(quality_summary.get("active_waivers"), list):
        return "delivery quality_summary.active_waivers must be a list"
    if not isinstance(quality_summary.get("residual_risks"), list):
        return "delivery quality_summary.residual_risks must be a list"
    return None


def _report_payload(metadata: Mapping[str, Any]) -> Mapping[str, Any]:
    nested = metadata.get("report")
    return nested if isinstance(nested, Mapping) else metadata


def _report_header_contract_error(report: Mapping[str, Any]) -> str | None:
    if not str(report.get("schema_version") or "").startswith("quality_gate_report/"):
        return "quality_report metadata requires a quality_gate_report schema_version"
    if not isinstance(report.get("passed"), bool):
        return "quality_report metadata requires a boolean passed field"
    if not isinstance(report.get("scenario"), str) or not str(report.get("scenario") or "").strip():
        return "quality_report metadata requires a scenario"
    results = report.get("results")
    if not isinstance(results, list) or not results:
        return "quality_report metadata requires a non-empty results list"
    return None


def _result_contract_error(result: Any, index: int) -> str | None:
    if not isinstance(result, Mapping):
        return f"quality_report results[{index}] must be an object"
    if not isinstance(result.get("name"), str) or not str(result.get("name") or "").strip():
        return f"quality_report results[{index}] requires a name"
    if str(result.get("status") or "") not in ALLOWED_RESULT_STATUSES:
        return f"quality_report results[{index}] has an invalid status"
    if not isinstance(result.get("blocking"), bool):
        return f"quality_report results[{index}] requires a boolean blocking field"
    if not isinstance(result.get("details"), Mapping):
        return f"quality_report results[{index}] requires details"
    return None


def _empty_summary(reason: str, *, artifact_id: Any = None) -> dict[str, Any]:
    return {
        "passed": False,
        "failure_category": "evidence_failure",
        "reason": reason,
        "artifact_id": artifact_id,
        "blocking_results": [],
        "findings": [],
        "blocking_findings": [],
        "debt_summary": {"added": 0, "reduced": 0, "unchanged": 0},
        "active_waivers": [],
        "expired_waivers": [],
        "invalid_waivers": [],
    }


def _blocking_results(results: list[Mapping[str, Any]]) -> list[dict[str, Any]]:
    return [
        {
            "name": item.get("name"),
            "status": item.get("status"),
            "owner": item.get("owner"),
            "message": item.get("message"),
        }
        for item in results
        if bool(item.get("blocking"))
        and str(item.get("status")) in {"failed", "timeout", "infra_error"}
    ]


def _collect_evidence(
    results: list[Mapping[str, Any]], report: Mapping[str, Any]
) -> dict[str, Any]:
    findings: list[dict[str, Any]] = []
    blocking_findings: list[dict[str, Any]] = []
    active_waivers: list[Any] = []
    expired_waivers: list[Any] = []
    invalid_waivers: list[Any] = []
    debt_summary = {"added": 0, "reduced": 0, "unchanged": 0}
    for result in results:
        details = result.get("details")
        if not isinstance(details, Mapping):
            continue
        structured_findings = _structured_items(details.get("findings"))
        findings.extend(structured_findings)
        if bool(result.get("blocking")):
            blocking_findings.extend(item for item in structured_findings if _finding_is_blocking(item))
        _extend_evidence(active_waivers, details.get("active_waivers"))
        _extend_evidence(active_waivers, details.get("exemptions_applied"))
        _extend_evidence(expired_waivers, details.get("expired_waivers"))
        _extend_evidence(invalid_waivers, details.get("invalid_waivers"))
        _merge_debt_summary(debt_summary, details.get("debt_summary"))
    _extend_evidence(expired_waivers, report.get("expired_waivers"))
    _extend_evidence(active_waivers, report.get("active_waivers"))
    _extend_evidence(invalid_waivers, report.get("invalid_waivers"))
    return {
        "findings": findings,
        "blocking_findings": blocking_findings,
        "debt_summary": debt_summary,
        "active_waivers": active_waivers,
        "expired_waivers": expired_waivers,
        "invalid_waivers": invalid_waivers,
    }


def _structured_items(value: Any) -> list[dict[str, Any]]:
    return [dict(item) for item in value if isinstance(item, Mapping)] if isinstance(value, list) else []


def _extend_evidence(target: list[Any], value: Any) -> None:
    if isinstance(value, list):
        target.extend(value)
    elif isinstance(value, int) and not isinstance(value, bool) and value > 0:
        target.extend({"count_only": True} for _ in range(value))


def _merge_debt_summary(target: dict[str, int], value: Any) -> None:
    if not isinstance(value, Mapping):
        return
    for key in target:
        raw = value.get(key)
        if isinstance(raw, bool):
            target[key] += int(raw)
        elif isinstance(raw, int):
            target[key] += raw
        elif isinstance(raw, list):
            target[key] += len(raw)


def _finding_is_blocking(finding: Mapping[str, Any]) -> bool:
    waiver = finding.get("waiver")
    if isinstance(waiver, Mapping) and str(waiver.get("status") or "").lower() == "active":
        return False
    disposition = str(finding.get("status") or finding.get("disposition") or "open").lower()
    if disposition in RESOLVED_FINDING_STATUSES:
        return False
    if finding.get("blocking") is True:
        return True
    delta = finding.get("delta")
    return isinstance(delta, Mapping) and str(delta.get("direction") or "") in {"added", "increased"}


def _failure_reason(
    report: Mapping[str, Any],
    blocking_results: list[dict[str, Any]],
    infrastructure_results: list[dict[str, Any]],
    evidence: Mapping[str, Any],
) -> tuple[str | None, str]:
    checks = (
        (infrastructure_results, "infrastructure_failure", "blocking quality checks had infrastructure failures"),
        (evidence["expired_waivers"], "code_quality_failure", "quality waivers are expired"),
        (evidence["invalid_waivers"], "code_quality_failure", "quality waivers have invalid baselines"),
        (evidence["blocking_findings"], "code_quality_failure", "unresolved blocking quality findings remain"),
    )
    for items, category, message in checks:
        if items:
            return category, f"{len(items)} {message}"
    if blocking_results or not bool(report.get("passed")):
        return "code_quality_failure", f"{len(blocking_results)} blocking quality checks failed"
    return None, "quality report passed"


def _review_finding_is_unresolved(finding: Any) -> bool:
    if not isinstance(finding, Mapping):
        return True
    severity = str(finding.get("severity") or "").lower()
    disposition = str(finding.get("status") or finding.get("disposition") or "open").lower()
    blocking = bool(finding.get("blocking")) or severity in {"blocking", "critical"}
    return blocking and disposition not in {"resolved", "waived", "closed"}
