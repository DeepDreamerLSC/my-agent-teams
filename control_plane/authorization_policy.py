from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterable, Mapping


AUTHORIZATION_POLICY_VERSION = "delegated_authorization/v1"

L0_AUTO = "L0_AUTO"
L1_REVIEWER_COORDINATOR = "L1_REVIEWER_COORDINATOR"
L2_OWNER = "L2_OWNER"


@dataclass(frozen=True)
class AuthorizationRule:
    rule_id: str
    level: str
    action: str
    action_type: str
    environments: tuple[str, ...]
    target_scopes: tuple[str, ...]
    reversible: bool | None
    description: str
    required_evidence: tuple[str, ...] = ()

    def public_dict(self, *, enabled: bool = True) -> dict[str, Any]:
        return {
            "rule_id": self.rule_id,
            "level": self.level,
            "action": self.action,
            "action_type": self.action_type,
            "environments": list(self.environments),
            "target_scopes": list(self.target_scopes),
            "reversible": self.reversible,
            "description": self.description,
            "required_evidence": list(self.required_evidence),
            "enabled": enabled,
            "policy_version": AUTHORIZATION_POLICY_VERSION,
        }


AUTHORIZATION_RULES: tuple[AuthorizationRule, ...] = (
    AuthorizationRule(
        "l0.read_only_check.task_workspace",
        L0_AUTO,
        "READ_ONLY_CHECK",
        "inspection",
        ("local", "dev", "test"),
        ("task_workspace",),
        True,
        "当前任务工作区内的只读检查，低风险且可逆。",
    ),
    AuthorizationRule(
        "l0.run_tests.task_workspace",
        L0_AUTO,
        "RUN_TESTS",
        "verification",
        ("local", "dev", "test"),
        ("task_workspace",),
        True,
        "当前任务工作区内运行测试，不修改正式环境。",
    ),
    AuthorizationRule(
        "l0.generate_temp_artifact.task_workspace",
        L0_AUTO,
        "GENERATE_TEMP_ARTIFACT",
        "artifact",
        ("local", "dev", "test"),
        ("task_workspace", "temporary_directory"),
        True,
        "仅生成临时制品，目标受任务工作区或临时目录约束。",
    ),
    AuthorizationRule(
        "l0.retry_local_ci.task_workspace",
        L0_AUTO,
        "RETRY_LOCAL_CI",
        "ci",
        ("local", "dev", "test"),
        ("task_workspace",),
        True,
        "仅重试当前任务的本地 CI。",
    ),
    AuthorizationRule(
        "l0.restart_local_service.task_workspace",
        L0_AUTO,
        "RESTART_LOCAL_SERVICE",
        "service_control",
        ("local", "dev"),
        ("task_workspace",),
        True,
        "仅启动或重启当前任务工作区内的本地服务。",
    ),
    AuthorizationRule(
        "l1.restart_test_service.registered_environment",
        L1_REVIEWER_COORDINATOR,
        "RESTART_TEST_SERVICE",
        "service_control",
        ("test",),
        ("registered_test_environment",),
        True,
        "测试环境服务重启需要 Reviewer 或 Coordinator 明确批准。",
    ),
    AuthorizationRule(
        "l1.restore_test_snapshot.verified_snapshot",
        L1_REVIEWER_COORDINATOR,
        "RESTORE_TEST_SNAPSHOT",
        "environment_restore",
        ("test",),
        ("verified_test_snapshot",),
        True,
        "仅允许按已验证快照恢复测试环境。",
        ("snapshot_verified",),
    ),
    AuthorizationRule(
        "l1.controlled_fault_injection.registered_environment",
        L1_REVIEWER_COORDINATOR,
        "CONTROLLED_FAULT_INJECTION",
        "fault_injection",
        ("test",),
        ("registered_test_environment",),
        True,
        "受控故障注入仅限测试环境并要求委托审批。",
    ),
    AuthorizationRule(
        "l1.merge_pr.frozen_head",
        L1_REVIEWER_COORDINATOR,
        "MERGE_PR",
        "merge",
        ("repository",),
        ("exact_pr_head",),
        False,
        "PR 合入必须绑定冻结 HEAD，并满足独立审查、CI 与 merge-gate。",
        ("review_approved", "local_ci_fresh", "merge_gate_ready", "pr_open_mergeable"),
    ),
)


HIGH_RISK_ACTIONS = {
    "DEPLOY_PRODUCTION",
    "WRITE_PRODUCTION",
    "DELETE_IRREVERSIBLE",
    "OVERWRITE_IRREVERSIBLE",
    "CHANGE_CREDENTIAL",
    "CHANGE_SECRET",
    "CHANGE_PERMISSION",
    "MIGRATE_REAL_DATA",
    "BULK_FIX_REAL_DATA",
    "EXPAND_PUBLIC_ACCESS",
    "BYPASS_GATE",
    "WAIVE_POLICY",
}


def _normalized(value: Any) -> str:
    return str(value or "").strip()


def _enabled_rule_ids(
    rules: Iterable[AuthorizationRule], overrides: Mapping[str, bool]
) -> set[str]:
    return {rule.rule_id for rule in rules if overrides.get(rule.rule_id, True)}


def classify_authorization(
    request: Mapping[str, Any], *, overrides: Mapping[str, bool] | None = None
) -> dict[str, Any]:
    """Route one exact request through the small, explicit policy table.

    Missing or unknown information never broadens authority: it is routed to
    L2 and remains non-grantable until the missing fields are supplied.
    """

    overrides = dict(overrides or {})
    action = _normalized(request.get("action")).upper()
    action_type = _normalized(request.get("action_type")).lower()
    environment = _normalized(request.get("environment")).lower()
    target_scope = _normalized(request.get("target_scope")).lower()
    exact_targets = request.get("exact_targets")
    reversible = request.get("reversible")
    expires_at = _normalized(request.get("expires_at"))
    required = {
        "action": action,
        "action_type": action_type,
        "environment": environment,
        "target_scope": target_scope,
        "exact_targets": exact_targets if isinstance(exact_targets, list) and exact_targets else None,
        "reason": _normalized(request.get("reason")),
        "reversible": reversible if isinstance(reversible, bool) else None,
        "expires_at": expires_at,
    }
    incomplete_fields = [key for key, value in required.items() if value in (None, "")]
    if incomplete_fields:
        return {
            "level": L2_OWNER,
            "risk_level": "unknown",
            "matched_rule_id": None,
            "policy_version": AUTHORIZATION_POLICY_VERSION,
            "routing_reason": "信息不完整，默认 fail-closed 路由到 Owner。",
            "incomplete_fields": incomplete_fields,
            "required_evidence": [],
            "grantable": False,
        }

    if request.get("scope_violation"):
        return {
            "level": L2_OWNER,
            "risk_level": "unknown",
            "matched_rule_id": None,
            "policy_version": AUTHORIZATION_POLICY_VERSION,
            "routing_reason": str(
                request.get("scope_violation_reason")
                or "exact_targets 超出已注册项目/任务/测试环境作用域，默认 fail-closed。"
            ),
            "incomplete_fields": sorted(
                set(["exact_targets", *list(request.get("scope_violation_fields") or [])])
            ),
            "required_evidence": [],
            "grantable": False,
        }

    if request.get("scope_validated") is not True:
        return {
            "level": L2_OWNER,
            "risk_level": "unknown",
            "matched_rule_id": None,
            "policy_version": AUTHORIZATION_POLICY_VERSION,
            "routing_reason": "exact_targets 尚未经过项目与任务作用域校验，默认 fail-closed。",
            "incomplete_fields": ["scope_validation"],
            "required_evidence": [],
            "grantable": False,
        }

    if bool(request.get("manual_only")):
        return {
            "level": L2_OWNER,
            "risk_level": "critical",
            "matched_rule_id": None,
            "policy_version": AUTHORIZATION_POLICY_VERSION,
            "routing_reason": "manual_only 请求必须由 Owner 人工决定。",
            "incomplete_fields": [],
            "required_evidence": [],
            "grantable": True,
        }

    if action in HIGH_RISK_ACTIONS or environment in {"prod", "production"}:
        return {
            "level": L2_OWNER,
            "risk_level": "critical",
            "matched_rule_id": None,
            "policy_version": AUTHORIZATION_POLICY_VERSION,
            "routing_reason": "生产、不可逆、凭据/权限、真实数据或门禁豁免请求必须由 Owner 批准。",
            "incomplete_fields": [],
            "required_evidence": [],
            "grantable": True,
        }

    enabled = _enabled_rule_ids(AUTHORIZATION_RULES, overrides)
    for rule in AUTHORIZATION_RULES:
        if rule.rule_id not in enabled:
            continue
        if action != rule.action:
            continue
        if action_type != rule.action_type:
            continue
        if environment not in rule.environments or target_scope not in rule.target_scopes:
            continue
        if rule.reversible is not None and reversible is not rule.reversible:
            continue
        return {
            "level": rule.level,
            "risk_level": "low" if rule.level == L0_AUTO else "high" if rule.action == "MERGE_PR" else "medium",
            "matched_rule_id": rule.rule_id,
            "policy_version": AUTHORIZATION_POLICY_VERSION,
            "routing_reason": rule.description,
            "incomplete_fields": [],
            "required_evidence": list(rule.required_evidence),
            "grantable": True,
        }

    return {
        "level": L2_OWNER,
        "risk_level": "unknown",
        "matched_rule_id": None,
        "policy_version": AUTHORIZATION_POLICY_VERSION,
        "routing_reason": "未命中 action + environment + target_scope 显式规则，默认由 Owner 决定。",
        "incomplete_fields": [],
        "required_evidence": [],
        "grantable": True,
    }
