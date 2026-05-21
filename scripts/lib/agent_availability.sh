#!/bin/bash
# shellcheck shell=bash
# agent_availability.sh - shared busy-aware agent availability helper.
#
# This file is designed to be sourced by shell scripts and can also be executed
# as a tiny CLI for diagnostics.

_AGENT_AVAILABILITY_LIB_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
_AGENT_AVAILABILITY_WORKSPACE_ROOT="$(cd "$_AGENT_AVAILABILITY_LIB_DIR/../.." && pwd)"

agent_availability_tasks_root() {
    printf '%s\n' "${TASKS_ROOT:-${AGENT_AVAILABILITY_TASKS_ROOT:-$_AGENT_AVAILABILITY_WORKSPACE_ROOT/tasks}}"
}

agent_availability_config_path() {
    printf '%s\n' "${CONFIG_PATH:-${AGENT_AVAILABILITY_CONFIG_PATH:-$_AGENT_AVAILABILITY_WORKSPACE_ROOT/config.json}}"
}

_agent_availability_eval() {
    local output_format="$1"
    local agent_id="$2"
    local tasks_root="${3:-$(agent_availability_tasks_root)}"
    local config_path="${4:-$(agent_availability_config_path)}"

    python3 - "$tasks_root" "$config_path" "$agent_id" "$output_format" <<'PY'
import json
import os
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path


def clean(value):
    if value is None:
        return ''
    return str(value).strip()


def parse_iso(value):
    text = clean(value)
    if not text:
        return None
    try:
        parsed = datetime.fromisoformat(text)
    except Exception:
        return None
    if parsed.tzinfo is None:
        try:
            parsed = parsed.astimezone()
        except Exception:
            pass
    return parsed


def list_of_strings(value):
    if isinstance(value, list):
        return [clean(item) for item in value if clean(item)]
    text = clean(value)
    return [text] if text else []


def join_csv(values):
    return ','.join(str(item) for item in values if str(item))


def unique_preserve(values):
    seen = set()
    result = []
    for item in values:
        if item in seen:
            continue
        seen.add(item)
        result.append(item)
    return result


def bool_flag(value):
    return '1' if value else '0'


def role_members(config):
    members = defaultdict(list)
    for agent_name, payload in (config.get('agents') or {}).items():
        if not isinstance(payload, dict):
            continue
        role = clean(payload.get('role')).lower()
        if role:
            members[role].append(clean(agent_name))
    return {key: unique_preserve(value) for key, value in members.items()}


def pick_role(config, agent_id):
    agents = config.get('agents') or {}
    payload = agents.get(agent_id)
    if isinstance(payload, dict):
        return clean(payload.get('role')).lower()
    for name, meta in agents.items():
        if not isinstance(meta, dict):
            continue
        if clean(meta.get('tmux_session')) == agent_id or clean(name) == agent_id:
            return clean(meta.get('role')).lower()
    return ''


def first_or_empty(values):
    return values[0] if len(values) == 1 else ''


def review_matches(task, agent_id, sole_reviewer):
    reviewers = [item for item in unique_preserve([clean(task.get('reviewer')), *list_of_strings(task.get('reviewers'))]) if item]
    if not reviewers and task.get('review_required') and sole_reviewer:
        reviewers = [sole_reviewer]
    return agent_id in reviewers


def qa_matches(task, agent_id, agent_role, sole_qa):
    explicit = [item for item in unique_preserve(
        [
            clean(task.get('qa_agent')),
            clean(task.get('qa_assignee')),
            clean(task.get('qa_owner')),
            clean(task.get('verify_agent')),
            clean(task.get('verify_owner')),
            clean(task.get('tester')),
        ]
    ) if item]
    if explicit:
        return agent_id in explicit
    return bool(agent_role == 'qa' and sole_qa and agent_id == sole_qa)


def pm_matches(task, agent_id, agent_role, sole_pm):
    explicit = [item for item in unique_preserve(
        [
            clean(task.get('owner_pm')),
            clean(task.get('pm')),
            clean(task.get('acceptance_owner')),
        ]
    ) if item]
    if explicit:
        return agent_id in explicit
    return bool(agent_role in {'pm', 'pm-chief'} and sole_pm and agent_id == sole_pm)


def capacity_limits(config, agent_id):
    pool = config.get('task_pool') or {}
    agents = config.get('agents') or {}
    wip_limits = config.get('wip_limits') or {}

    def as_int(value, default):
        try:
            if value in (None, ''):
                return default
            return int(value)
        except Exception:
            return default

    working_limit = max(1, as_int(pool.get('default_working_limit'), 1))
    reserved_limit = max(1, as_int(pool.get('default_reserved_limit'), 1))
    role = clean((agents.get(agent_id) or {}).get('role')).lower()
    role_keys = {
        'fullstack_dev': 'dev',
        'reviewer': 'reviewer',
        'qa': 'qa',
        'architect': 'architect',
        'pm': 'pm-chief',
        'pm-chief': 'pm-chief',
    }
    role_key = role_keys.get(role)
    role_limit = wip_limits.get(agent_id)
    if role_limit in (None, '') and role_key:
        role_limit = wip_limits.get(role_key)
    if role_limit not in (None, ''):
        working_limit = max(1, min(working_limit, as_int(role_limit, working_limit)))
    return {
        'working_limit': working_limit,
        'reserved_limit': reserved_limit,
        'active_limit': working_limit + reserved_limit,
        'note': 'metadata_only_not_used_for_busy_level',
    }


def ready_gate_code(task):
    merge_gate = clean(task.get('merge_gate_state'))
    review_state = clean(task.get('review_gate_state')).lower()
    qa_state = clean(task.get('qa_gate_state')).lower()
    if merge_gate == 'quality_pending':
        return 'quality_pending'
    if merge_gate == 'review_pending' or review_state == 'pending':
        return 'review_pending'
    if merge_gate == 'qa_pending' or qa_state in {'missing', 'pending'}:
        return 'qa_pending'
    if merge_gate == 'pm_acceptance_pending':
        return 'pm_acceptance_pending'
    return 'ready_for_merge'


def blocked_gate_code(task):
    merge_gate = clean(task.get('merge_gate_state'))
    review_state = clean(task.get('review_gate_state')).lower()
    qa_state = clean(task.get('qa_gate_state')).lower()
    if merge_gate == 'review_rejected' or review_state in {'rejected', 'failed', 'fail'}:
        return 'review_rejected'
    if merge_gate == 'qa_failed' or qa_state == 'failed':
        return 'qa_failed'
    return 'blocked'


def active_pre_reservation(task, now):
    agent = clean(task.get('pre_reserved_by'))
    if not agent:
        return False, ''
    until_raw = clean(task.get('pre_reserved_until') or task.get('pre_reserved_expires_at'))
    if not until_raw:
        return True, agent
    until_dt = parse_iso(until_raw)
    if until_dt is None:
        return True, agent
    return now < until_dt, agent


def add_reason(bucket, bucket_tasks, task_id, code):
    if not code:
        return
    token = f'{code}:{task_id}' if task_id else code
    bucket.append(token)
    if task_id:
        bucket_tasks.add(task_id)


def flatten(payload):
    ordered = [
        ('agent_id', payload['agent_id']),
        ('role', payload['role']),
        ('busy_level', payload['busy_level']),
        ('primary_reason', payload['primary_reason']),
        ('hard_task_count', payload['hard_task_count']),
        ('soft_task_count', payload['soft_task_count']),
        ('hard_task_ids', join_csv(payload['hard_task_ids'])),
        ('soft_task_ids', join_csv(payload['soft_task_ids'])),
        ('reason_codes', join_csv(payload['reason_codes'])),
        ('hard_reason_codes', join_csv(payload['hard_reason_codes'])),
        ('soft_reason_codes', join_csv(payload['soft_reason_codes'])),
        ('assigned_working_count', payload['counts']['assigned_working']),
        ('assigned_dispatched_count', payload['counts']['assigned_dispatched']),
        ('assigned_ready_for_merge_count', payload['counts']['assigned_ready_for_merge']),
        ('assigned_blocked_count', payload['counts']['assigned_blocked']),
        ('pre_reserved_active_count', payload['counts']['pre_reserved_active']),
        ('review_pending_count', payload['counts']['review_pending']),
        ('qa_pending_count', payload['counts']['qa_pending']),
        ('pm_acceptance_pending_count', payload['counts']['pm_acceptance_pending']),
        ('result_pending_count', payload['counts']['result_pending']),
        ('working_limit', payload['capacity']['working_limit']),
        ('reserved_limit', payload['capacity']['reserved_limit']),
        ('active_limit', payload['capacity']['active_limit']),
        ('capacity_note', payload['capacity']['note']),
        ('execute_route', payload['routes']['execute']),
        ('remind_route', payload['routes']['remind']),
        ('preheat_route', payload['routes']['preheat']),
        ('broadcast_route', payload['routes']['broadcast']),
        ('critical_route', payload['routes']['critical']),
        ('can_direct_execute', bool_flag(payload['can_direct_execute'])),
        ('can_direct_remind', bool_flag(payload['can_direct_remind'])),
        ('queue_only', bool_flag(payload['queue_only'])),
    ]
    return '\n'.join(f'{key}={value}' for key, value in ordered)


tasks_root = Path(sys.argv[1]).expanduser()
config_path = Path(sys.argv[2]).expanduser()
agent_id = clean(sys.argv[3])
output_format = clean(sys.argv[4]).lower() or 'kv'
ignore_task_ids = set()
for raw in (os.environ.get('AGENT_AVAILABILITY_IGNORE_TASK_ID'), os.environ.get('AGENT_AVAILABILITY_IGNORE_TASK_IDS')):
    if not raw:
        continue
    for item in str(raw).split(','):
        cleaned = clean(item)
        if cleaned:
            ignore_task_ids.add(cleaned)

config = {}
if config_path.exists():
    try:
        config = json.loads(config_path.read_text(encoding='utf-8'))
    except Exception:
        config = {}

agent_role = pick_role(config, agent_id)
role_map = role_members(config)
sole_reviewer = first_or_empty(role_map.get('reviewer', []))
sole_qa = first_or_empty(role_map.get('qa', []))
sole_pm = first_or_empty(role_map.get('pm', []) or role_map.get('pm-chief', []))

now = parse_iso(os.environ.get('AGENT_AVAILABILITY_NOW'))
if now is None:
    now = datetime.now().astimezone()

terminal_statuses = {'done', 'merged', 'archived', 'cancelled', 'closed'}
hard_reasons = []
soft_reasons = []
hard_task_ids = set()
soft_task_ids = set()
counts = defaultdict(int)

if tasks_root.exists():
    for task_path in sorted(tasks_root.glob('*/task.json')):
        try:
            task = json.loads(task_path.read_text(encoding='utf-8'))
        except Exception:
            continue
        task_dir = task_path.parent
        task_id = clean(task.get('id')) or task_dir.name
        if task_id in ignore_task_ids or task_dir.name in ignore_task_ids:
            continue
        status = clean(task.get('status')).lower()
        assigned_agent = clean(task.get('assigned_agent'))
        reserved_by = clean(task.get('reserved_by'))
        claimed_by = clean(task.get('claimed_by'))
        pre_reserved_active, pre_reserved_agent = active_pre_reservation(task, now)
        ack_exists = (task_dir / 'ack.json').exists()
        result_exists = (task_dir / 'result.json').exists()

        assigned_related = agent_id in {assigned_agent, reserved_by, claimed_by}
        reviewer_related = review_matches(task, agent_id, sole_reviewer)
        qa_related = qa_matches(task, agent_id, agent_role, sole_qa)
        pm_related = pm_matches(task, agent_id, agent_role, sole_pm)

        if status not in terminal_statuses and pre_reserved_active and pre_reserved_agent == agent_id:
            counts['pre_reserved_active'] += 1
            add_reason(hard_reasons, hard_task_ids, task_id, 'pre_reserved_active')

        if assigned_related:
            if status == 'working':
                counts['assigned_working'] += 1
                if result_exists:
                    counts['result_pending'] += 1
                    add_reason(soft_reasons, soft_task_ids, task_id, 'result_pending')
                else:
                    add_reason(hard_reasons, hard_task_ids, task_id, 'working')
            elif status == 'dispatched':
                counts['assigned_dispatched'] += 1
                if result_exists:
                    counts['result_pending'] += 1
                    add_reason(soft_reasons, soft_task_ids, task_id, 'result_pending')
                elif ack_exists:
                    add_reason(hard_reasons, hard_task_ids, task_id, 'dispatched_ack_present')
                else:
                    add_reason(hard_reasons, hard_task_ids, task_id, 'dispatched_unacked')
            elif status == 'ready_for_merge':
                counts['assigned_ready_for_merge'] += 1
                gate_code = ready_gate_code(task)
                if gate_code == 'review_pending':
                    counts['review_pending'] += 1
                elif gate_code == 'qa_pending':
                    counts['qa_pending'] += 1
                elif gate_code == 'pm_acceptance_pending':
                    counts['pm_acceptance_pending'] += 1
                elif gate_code == 'quality_pending':
                    counts['review_pending'] += 1
                    counts['qa_pending'] += 1
                add_reason(soft_reasons, soft_task_ids, task_id, gate_code)
            elif status == 'blocked':
                counts['assigned_blocked'] += 1
                add_reason(soft_reasons, soft_task_ids, task_id, blocked_gate_code(task))
            elif status in {'pending', 'pooled', 'dependency_wait'}:
                if agent_id in {reserved_by, claimed_by}:
                    add_reason(hard_reasons, hard_task_ids, task_id, 'reserved_slot_active')
            elif status and status not in terminal_statuses:
                if result_exists:
                    counts['result_pending'] += 1
                    add_reason(soft_reasons, soft_task_ids, task_id, 'result_pending')
                elif ack_exists:
                    add_reason(hard_reasons, hard_task_ids, task_id, f'active_{status}')
                else:
                    add_reason(soft_reasons, soft_task_ids, task_id, f'active_{status}')

        if reviewer_related and status == 'ready_for_merge':
            gate_code = ready_gate_code(task)
            if gate_code in {'review_pending', 'quality_pending'}:
                counts['review_pending'] += 1
        if reviewer_related and status == 'blocked':
            gate_code = blocked_gate_code(task)
            if gate_code == 'review_rejected':
                counts['review_pending'] += 1

        if qa_related and status == 'ready_for_merge':
            gate_code = ready_gate_code(task)
            if gate_code in {'qa_pending', 'quality_pending'}:
                counts['qa_pending'] += 1
        if qa_related and status == 'blocked':
            gate_code = blocked_gate_code(task)
            if gate_code == 'qa_failed':
                counts['qa_pending'] += 1

        if pm_related and status == 'ready_for_merge':
            gate_code = ready_gate_code(task)
            if gate_code == 'pm_acceptance_pending':
                counts['pm_acceptance_pending'] += 1
                add_reason(soft_reasons, soft_task_ids, task_id, gate_code)

hard_reasons = unique_preserve(hard_reasons)
soft_reasons = [item for item in unique_preserve(soft_reasons) if item not in set(hard_reasons)]
hard_task_list = sorted(hard_task_ids)
soft_task_list = sorted(task_id for task_id in soft_task_ids if task_id not in hard_task_ids)

if hard_reasons:
    busy_level = 'hard_busy'
elif soft_reasons:
    busy_level = 'soft_busy'
else:
    busy_level = 'idle'

routes = {
    'execute': 'direct' if busy_level == 'idle' else 'queue_only',
    'remind': 'direct' if busy_level == 'idle' else ('digest' if busy_level == 'soft_busy' else 'queue_only'),
    'preheat': 'direct' if busy_level == 'idle' else 'queue_only',
    'broadcast': 'direct',
    'critical': 'override',
}

payload = {
    'agent_id': agent_id,
    'role': agent_role,
    'busy_level': busy_level,
    'primary_reason': (hard_reasons[0] if hard_reasons else (soft_reasons[0] if soft_reasons else 'idle')),
    'reason_codes': unique_preserve([*hard_reasons, *soft_reasons]),
    'hard_reason_codes': hard_reasons,
    'soft_reason_codes': soft_reasons,
    'hard_task_ids': hard_task_list,
    'soft_task_ids': soft_task_list,
    'hard_task_count': len(hard_task_list),
    'soft_task_count': len(soft_task_list),
    'counts': {
        'assigned_working': int(counts['assigned_working']),
        'assigned_dispatched': int(counts['assigned_dispatched']),
        'assigned_ready_for_merge': int(counts['assigned_ready_for_merge']),
        'assigned_blocked': int(counts['assigned_blocked']),
        'pre_reserved_active': int(counts['pre_reserved_active']),
        'review_pending': int(counts['review_pending']),
        'qa_pending': int(counts['qa_pending']),
        'pm_acceptance_pending': int(counts['pm_acceptance_pending']),
        'result_pending': int(counts['result_pending']),
    },
    'capacity': capacity_limits(config, agent_id),
    'routes': routes,
    'can_direct_execute': routes['execute'] == 'direct',
    'can_direct_remind': routes['remind'] == 'direct',
    'queue_only': routes['execute'] == 'queue_only' and routes['remind'] == 'queue_only',
}

if output_format == 'json':
    print(json.dumps(payload, ensure_ascii=False, indent=2))
else:
    print(flatten(payload))
PY
}

classify_agent_availability() {
    local agent_id="$1"
    local tasks_root="${2:-$(agent_availability_tasks_root)}"
    local config_path="${3:-$(agent_availability_config_path)}"
    _agent_availability_eval kv "$agent_id" "$tasks_root" "$config_path"
}

classify_agent_availability_json() {
    local agent_id="$1"
    local tasks_root="${2:-$(agent_availability_tasks_root)}"
    local config_path="${3:-$(agent_availability_config_path)}"
    _agent_availability_eval json "$agent_id" "$tasks_root" "$config_path"
}

agent_availability_field() {
    local agent_id="$1"
    local field="$2"
    local tasks_root="${3:-$(agent_availability_tasks_root)}"
    local config_path="${4:-$(agent_availability_config_path)}"
    local payload_json=""

    payload_json="$(classify_agent_availability_json "$agent_id" "$tasks_root" "$config_path")"
    AGENT_AVAILABILITY_PAYLOAD_JSON="$payload_json" python3 - "$field" <<'PY'
import json
import os
import sys

field = sys.argv[1]
payload = json.loads(os.environ.get('AGENT_AVAILABILITY_PAYLOAD_JSON') or '{}')
value = payload
for part in field.split('.'):
    if isinstance(value, dict):
        value = value.get(part)
    else:
        value = None
        break
if isinstance(value, bool):
    print('1' if value else '0')
elif isinstance(value, list):
    print(','.join(str(item) for item in value))
elif value is None:
    print('')
else:
    print(value)
PY
}

agent_busy_level() {
    local agent_id="$1"
    local tasks_root="${2:-$(agent_availability_tasks_root)}"
    local config_path="${3:-$(agent_availability_config_path)}"
    agent_availability_field "$agent_id" busy_level "$tasks_root" "$config_path"
}

agent_delivery_route() {
    local agent_id="$1"
    local message_kind="$2"
    local tasks_root="${3:-$(agent_availability_tasks_root)}"
    local config_path="${4:-$(agent_availability_config_path)}"
    agent_availability_field "$agent_id" "routes.${message_kind}" "$tasks_root" "$config_path"
}

agent_can_direct_execute() {
    local agent_id="$1"
    local tasks_root="${2:-$(agent_availability_tasks_root)}"
    local config_path="${3:-$(agent_availability_config_path)}"
    [ "$(agent_delivery_route "$agent_id" execute "$tasks_root" "$config_path")" = "direct" ]
}

agent_can_direct_remind() {
    local agent_id="$1"
    local tasks_root="${2:-$(agent_availability_tasks_root)}"
    local config_path="${3:-$(agent_availability_config_path)}"
    [ "$(agent_delivery_route "$agent_id" remind "$tasks_root" "$config_path")" = "direct" ]
}

agent_remind_should_digest() {
    local agent_id="$1"
    local tasks_root="${2:-$(agent_availability_tasks_root)}"
    local config_path="${3:-$(agent_availability_config_path)}"
    [ "$(agent_delivery_route "$agent_id" remind "$tasks_root" "$config_path")" = "digest" ]
}

agent_availability_help() {
    cat <<'EOF_HELP'
usage:
  source scripts/lib/agent_availability.sh
  classify_agent_availability <agent_id> [tasks_root] [config_path]
  classify_agent_availability_json <agent_id> [tasks_root] [config_path]
  agent_busy_level <agent_id> [tasks_root] [config_path]
  agent_delivery_route <agent_id> <execute|remind|preheat|broadcast|critical> [tasks_root] [config_path]

cli:
  scripts/lib/agent_availability.sh classify <agent_id> [tasks_root] [config_path]
  scripts/lib/agent_availability.sh json <agent_id> [tasks_root] [config_path]
  scripts/lib/agent_availability.sh busy-level <agent_id> [tasks_root] [config_path]
  scripts/lib/agent_availability.sh route <agent_id> <execute|remind|preheat|broadcast|critical> [tasks_root] [config_path]
EOF_HELP
}

if [ "${BASH_SOURCE[0]}" = "$0" ]; then
    command="${1:-help}"
    case "$command" in
        classify)
            shift
            classify_agent_availability "${1:-}" "${2:-}" "${3:-}"
            ;;
        json)
            shift
            classify_agent_availability_json "${1:-}" "${2:-}" "${3:-}"
            ;;
        busy-level)
            shift
            agent_busy_level "${1:-}" "${2:-}" "${3:-}"
            ;;
        route)
            shift
            agent_delivery_route "${1:-}" "${2:-}" "${3:-}" "${4:-}"
            ;;
        help|-h|--help|'')
            agent_availability_help
            ;;
        *)
            printf 'unknown command: %s\n\n' "$command" >&2
            agent_availability_help >&2
            exit 2
            ;;
    esac
fi
