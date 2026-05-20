#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="${WORKSPACE_ROOT:-$(cd "$SCRIPT_DIR/.." && pwd)}"
TASKS_DIR="${TASKS_DIR:-$WORKSPACE_ROOT/tasks}"
TASK_ID="${1:-}"
TITLE="${2:-}"
ASSIGNED_AGENT="${3:-}"
DOMAIN="${4:-}"
PROJECT="${5:-}"
WRITE_SCOPE_CSV="${6:-}"
REVIEW_REQUIRED="${7:-}"
TEST_REQUIRED="${8:-}"
REVIEW_AUTHORITY="${9:-reviewer}"
EXECUTION_MODE="${10:-dev}"
TARGET_ENVIRONMENT="${11:-dev}"
REVIEW_LEVEL="${12:-}"
TASK_LEVEL="${13:-}"
REVIEWERS_CSV="${14:-}"
REVIEW_DEADLINE="${15:-}"
TASK_TYPE_RAW="${16:-}"
READ_ONLY_RAW="${17:-false}"
DOWNSTREAM_ACTION_RAW="${18:-}"
OWNER_APPROVAL_REQUIRED_RAW="${19:-false}"
OWNER_APPROVED_BY_RAW="${20:-}"
OWNER_APPROVED_AT_RAW="${21:-}"
CONFIG_PATH="${CONFIG_PATH:-$WORKSPACE_ROOT/config.json}"
STRICT_WRITE_SCOPE_CONFLICT="${STRICT_WRITE_SCOPE_CONFLICT:-0}"

if [ -z "$TASK_ID" ] || [ -z "$TITLE" ] || [ -z "$ASSIGNED_AGENT" ] || [ -z "$DOMAIN" ] || [ -z "$PROJECT" ]; then
  echo "usage: create-task.sh <task-id-title> <title> <assigned-agent> <domain> <project> [write-scope-csv] [review-required] [test-required] [review-authority] [execution-mode] [target-environment] [review-level] [task-level] [reviewers-csv] [review-deadline] [task-type] [read-only] [downstream-action] [owner-approval-required] [owner-approved-by] [owner-approved-at]" >&2
  echo "example: create-task.sh 修复Word生成质量问题 \"修复 Word 生成功能质量问题\" be-1 backend chiralium '' true true reviewer dev dev standard execution 'review-1' '2026-04-24T20:00:00+08:00' development false review" >&2
  exit 2
fi

TASK_DIR="$TASKS_DIR/$TASK_ID"
mkdir -p "$TASK_DIR"

python3 "$SCRIPT_DIR/lib/create_task_impl.py" "$CONFIG_PATH" "$TASK_ID" "$TITLE" "$ASSIGNED_AGENT" "$DOMAIN" "$PROJECT" "$WRITE_SCOPE_CSV" "$REVIEW_REQUIRED" "$TEST_REQUIRED" "$REVIEW_AUTHORITY" "$EXECUTION_MODE" "$TARGET_ENVIRONMENT" "$TASK_DIR" "$REVIEW_LEVEL" "$TASK_LEVEL" "$REVIEWERS_CSV" "$REVIEW_DEADLINE" "$STRICT_WRITE_SCOPE_CONFLICT" "$TASK_TYPE_RAW" "$READ_ONLY_RAW" "$DOWNSTREAM_ACTION_RAW" "$OWNER_APPROVAL_REQUIRED_RAW" "$OWNER_APPROVED_BY_RAW" "$OWNER_APPROVED_AT_RAW" "$WORKSPACE_ROOT"

echo "created $TASK_DIR"
