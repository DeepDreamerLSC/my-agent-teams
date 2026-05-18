from __future__ import annotations

from typing import Any


TASK_TYPE_DEFAULT_GATES: dict[str, tuple[bool | None, bool | None]] = {
    "development": (True, True),
    "design": (True, False),
    "integration": (True, True),
    "deployment": (True, True),
}


def parse_boolish(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    return str(value or "").strip().lower() in {"1", "true", "yes", "y", "on"}


def has_explicit_value(value: Any) -> bool:
    return value is not None and str(value).strip() != ""


def default_gate_flags(task_type: str) -> tuple[bool | None, bool | None]:
    return TASK_TYPE_DEFAULT_GATES.get(str(task_type or "").strip().lower(), (None, None))


def derive_quality_gate_mode(
    *,
    task_type: str,
    execution_mode: str,
    target_environment: str,
    task_level: str,
    review_required: bool,
    test_required: bool,
) -> str:
    if not (review_required and test_required):
        return "single"
    if str(target_environment or "").strip().lower() == "prod" or str(execution_mode or "").strip().lower() == "deploy":
        return "serial"
    if str(task_type or "").strip().lower() in {"deployment", "integration"} or str(task_level or "").strip().lower() == "integration":
        return "serial"
    return "parallel"


def validate_task_type_gate_template(
    *,
    task_type: str,
    review_required: bool,
    test_required: bool,
) -> list[str]:
    normalized_type = str(task_type or "").strip().lower()
    errors: list[str] = []
    if normalized_type == "verification":
        if review_required == test_required:
            errors.append("verification tasks require exactly one of review_required/test_required")
    elif normalized_type == "design":
        if not review_required:
            errors.append("design tasks require review_required=true")
        if test_required:
            errors.append("design tasks must use review-only gate (test_required=false)")
    elif normalized_type == "integration":
        if not review_required or not test_required:
            errors.append("integration tasks require both review_required=true and test_required=true")
    return errors


def resolve_gate_flags_for_create(
    *,
    task_type: str,
    review_required_raw: Any,
    test_required_raw: Any,
) -> tuple[bool, bool]:
    normalized_type = str(task_type or "").strip().lower()
    default_review, default_test = default_gate_flags(normalized_type)

    review_explicit = has_explicit_value(review_required_raw)
    test_explicit = has_explicit_value(test_required_raw)

    if review_explicit:
        review_required = parse_boolish(review_required_raw)
    elif default_review is not None:
        review_required = default_review
    else:
        review_required = False

    if test_explicit:
        test_required = parse_boolish(test_required_raw)
    elif default_test is not None:
        test_required = default_test
    else:
        test_required = False

    if normalized_type == "verification" and not (review_explicit or test_explicit):
        raise ValueError("verification tasks require an explicit main quality gate")

    return review_required, test_required
