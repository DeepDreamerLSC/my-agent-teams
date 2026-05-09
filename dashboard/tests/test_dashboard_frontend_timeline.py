from __future__ import annotations

import json
import subprocess
import textwrap
import unittest
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[2]
DASHBOARD_JS = REPO_ROOT / "dashboard" / "static" / "js" / "dashboard.js"
INDEX_HTML = REPO_ROOT / "dashboard" / "templates" / "index.html"


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

    def test_index_markup_contains_pool_and_pm_inbox_tabs(self):
        html = INDEX_HTML.read_text(encoding="utf-8")
        self.assertIn('data-tab="pool"', html)
        self.assertIn('data-tab="pm-inbox"', html)
        self.assertIn('id="pool-table"', html)
        self.assertIn('id="pm-inbox-table"', html)

    def test_gantt_filter_bar_markup_contains_quick_ranges_and_date_inputs(self):
        html = INDEX_HTML.read_text(encoding="utf-8")
        self.assertIn('id="gantt-filters"', html)
        for mode in ["today", "3d", "7d", "30d", "custom"]:
            self.assertIn(f'data-gantt-range="{mode}"', html)
        self.assertIn('id="gantt-start-date" type="date"', html)
        self.assertIn('id="gantt-end-date" type="date"', html)

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

    def test_render_pool_and_pm_inbox_views(self):
        script = textwrap.dedent(
            f"""
            const mod = require({json.dumps(str(DASHBOARD_JS))});
            global.document = {{
              getElementById(id) {{
                if (!this.nodes) this.nodes = {{}};
                if (!this.nodes[id]) this.nodes[id] = {{ innerHTML: '' }};
                return this.nodes[id];
              }},
              querySelector(selector) {{
                return this.getElementById(selector);
              }},
              createElement() {{
                return {{ textContent: '', innerHTML: '' }};
              }}
            }};
            mod.renderPoolView({{
              items: [{{
                task_id: 'pool-1',
                title: '待认领',
                priority: 'high',
                pool_wait_minutes: 12,
                claim_scope: ['dev-1'],
                eligible_agents: ['dev-1'],
                blocked_reasons: [],
                next_action: '等待认领'
              }}]
            }});
            mod.renderPmInboxView({{
              items: [{{
                task_id: 'blocked-1',
                title: '需仲裁',
                severity: 'L3',
                reason_type: 'blocked',
                summary: 'review_rejected',
                age_minutes: 8,
                recommended_action: '补修'
              }}]
            }});
            console.log(JSON.stringify({{
              poolHtml: document.getElementById('#pool-table tbody').innerHTML,
              inboxHtml: document.getElementById('#pm-inbox-table tbody').innerHTML
            }}));
            """
        )
        result = _run_node(script)
        self.assertIn('待认领', result['poolHtml'])
        self.assertIn('dev-1', result['poolHtml'])
        self.assertIn('需仲裁', result['inboxHtml'])
        self.assertIn('review_rejected', result['inboxHtml'])

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

    def test_gantt_time_filter_includes_intersecting_phase_intervals(self):
        script = textwrap.dedent(
            f"""
            const mod = require({json.dumps(str(DASHBOARD_JS))});
            const payload = [
              {{ title: 'old', milestones: {{ created: '2026-05-01T09:00:00', dispatched: '2026-05-01T10:00:00' }} }},
              {{ title: 'match', milestones: {{ created: '2026-05-04T09:00:00', dispatched: '2026-05-04T10:00:00' }} }},
              {{ title: 'span', milestones: {{ created: '2026-05-03T23:00:00', dispatched: '2026-05-04T01:00:00' }} }}
            ];
            const filtered = mod.applyGanttTimeFilter(payload, {{ mode: 'custom', customStart: '2026-05-04', customEnd: '2026-05-04' }});
            console.log(JSON.stringify({{
              titles: filtered.items.map(item => item.title).sort(),
              label: filtered.range.label,
              hasWarning: Boolean(filtered.range.warning)
            }}));
            """
        )
        result = _run_node(script)
        self.assertEqual(result["titles"], ["match", "span"])
        self.assertIn("2026-05-04", result["label"])
        self.assertFalse(result["hasWarning"])

    def test_gantt_custom_filter_warns_and_degrades_for_invalid_range(self):
        script = textwrap.dedent(
            f"""
            const mod = require({json.dumps(str(DASHBOARD_JS))});
            const payload = [{{ title: 'task', milestones: {{ created: '2026-05-04T09:00:00' }} }}];
            const filtered = mod.applyGanttTimeFilter(payload, {{ mode: 'custom', customStart: '2026-05-05', customEnd: '2026-05-04' }});
            console.log(JSON.stringify({{
              count: filtered.items.length,
              warning: filtered.range.warning,
              startIsNull: filtered.range.start === null,
              endIsNull: filtered.range.end === null
            }}));
            """
        )
        result = _run_node(script)
        self.assertEqual(result["count"], 1)
        self.assertIn("开始日期", result["warning"])
        self.assertTrue(result["startIsNull"])
        self.assertTrue(result["endIsNull"])

    def test_gantt_quick_ranges_include_today_and_phase_palette_matches_design_tokens(self):
        script = textwrap.dedent(
            f"""
            const mod = require({json.dumps(str(DASHBOARD_JS))});
            const range = mod.getGanttDateRange({{ mode: '3d' }}, new Date(2026, 4, 7, 12, 0, 0));
            console.log(JSON.stringify({{
              label: range.label,
              startDay: range.start.getDate(),
              endDay: range.end.getDate(),
              startHour: range.start.getHours(),
              endHour: range.end.getHours(),
              colors: mod.GANTT_PHASES.map(phase => phase.color)
            }}));
            """
        )
        result = _run_node(script)
        self.assertEqual(result["label"], "近三天")
        self.assertEqual(result["startDay"], 5)
        self.assertEqual(result["endDay"], 7)
        self.assertEqual(result["startHour"], 0)
        self.assertEqual(result["endHour"], 23)
        self.assertEqual(result["colors"], ["#1677ff", "#13c2c2", "#722ed1", "#faad14", "#52c41a", "#ff4d4f"])
