from __future__ import annotations

import json
import subprocess
import textwrap
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DASHBOARD_JS = REPO_ROOT / "dashboard" / "static" / "js" / "dashboard.js"


def _run_node(script: str) -> dict:
    completed = subprocess.run(
        ["node", "-e", script],
        cwd=str(REPO_ROOT),
        capture_output=True,
        text=True,
        check=True,
    )
    return json.loads(completed.stdout)


class DashboardFrontendTimelineTests(unittest.TestCase):
    def test_sort_timeline_items_orders_by_timestamp_then_event_id(self):
        script = textwrap.dedent(
            f"""
            const mod = require({json.dumps(str(DASHBOARD_JS))});
            const sorted = mod.sortTimelineItems([
              {{ event_id: 'comm-2', happened_at: '2026-05-04T00:15:00+08:00' }},
              {{ event_id: 'comm-1', happened_at: '2026-05-04T00:10:00+08:00' }},
              {{ event_id: 'comm-3', happened_at: '2026-05-04T00:15:00+08:00' }}
            ]).map(item => item.event_id);
            console.log(JSON.stringify({{ sorted }}));
            """
        )
        result = _run_node(script)
        self.assertEqual(result["sorted"], ["comm-1", "comm-2", "comm-3"])

    def test_render_timeline_html_sorts_and_renders_status_and_empty_state(self):
        script = textwrap.dedent(
            f"""
            const mod = require({json.dumps(str(DASHBOARD_JS))});
            const emptyHtml = mod.renderTimelineHtml([], 'status');
            const statusHtml = mod.renderTimelineHtml([
              {{ event_id: 'status-2', event_type: 'ack', source: 'ack_json', status_from: 'dispatched', status_to: 'working', summary: '已接单', happened_at: '2026-05-04T00:20:00+08:00' }},
              {{ event_id: 'status-1', event_type: 'created', source: 'task_json', status_from: '', status_to: 'pending', summary: '任务创建', happened_at: '2026-05-04T00:10:00+08:00' }}
            ], 'status');
            console.log(JSON.stringify({{
              emptyHasFallback: emptyHtml.includes('暂无记录'),
              statusHasSummary: statusHtml.includes('已接单'),
              statusHasTransition: statusHtml.includes('dispatched') && statusHtml.includes('working'),
              statusOrderOk: statusHtml.indexOf('任务创建') < statusHtml.indexOf('已接单')
            }}));
            """
        )
        result = _run_node(script)
        self.assertTrue(result["emptyHasFallback"])
        self.assertTrue(result["statusHasSummary"])
        self.assertTrue(result["statusHasTransition"])
        self.assertTrue(result["statusOrderOk"])

    def test_render_timeline_html_renders_communication_fields(self):
        script = textwrap.dedent(
            f"""
            const mod = require({json.dumps(str(DASHBOARD_JS))});
            const communicationHtml = mod.renderTimelineHtml([
              {{ event_type: 'question', from_actor: 'dev-1', to_actor: 'review-1', channel: 'task', severity: 'info', priority: 'high', message_text: '请帮忙确认', happened_at: '2026-05-04T00:15:00+08:00' }}
            ], 'communication');
            console.log(JSON.stringify({{
              hasActors: communicationHtml.includes('dev-1') && communicationHtml.includes('review-1'),
              hasMessage: communicationHtml.includes('请帮忙确认'),
              hasPriority: communicationHtml.includes('priority=high')
            }}));
            """
        )
        result = _run_node(script)
        self.assertTrue(result["hasActors"])
        self.assertTrue(result["hasMessage"])
        self.assertTrue(result["hasPriority"])

    def test_render_task_detail_html_handles_missing_durations_and_empty_communication(self):
        script = textwrap.dedent(
            f"""
            const mod = require({json.dumps(str(DASHBOARD_JS))});
            const html = mod.renderTaskDetailHtml({{
              task: {{
                task_id: 'task-1',
                title: '任务一',
                project: 'my-agent-teams',
                domain: 'development',
                assigned_agent: 'dev-1',
                owner_pm: 'pm-chief',
                reviewer: 'review-1',
                current_status: 'working',
                board_status: 'working',
                created_at: '2026-05-04T00:00:00+08:00',
                current_status_at: '2026-05-04T00:10:00+08:00',
                communication_count: 0,
                summary: ''
              }},
              durations: {{
                create_to_dispatch_hours: null,
                dispatch_to_ack_hours: null,
                ack_to_result_hours: null,
                result_to_review_hours: null,
                review_to_verify_hours: null,
                verify_to_close_hours: null,
                total_cycle_hours: null
              }},
              statusTimeline: [],
              communicationTimeline: []
            }});
            console.log(JSON.stringify({{
              hasFallbackDuration: html.includes('>-<'),
              hasEmptyCommunication: html.includes('沟通时间线') && html.includes('暂无记录'),
              hasTaskId: html.includes('task-1'),
              hasOwnerPm: html.includes('pm-chief')
            }}));
            """
        )
        result = _run_node(script)
        self.assertTrue(result["hasFallbackDuration"])
        self.assertTrue(result["hasEmptyCommunication"])
        self.assertTrue(result["hasTaskId"])
        self.assertTrue(result["hasOwnerPm"])
