from __future__ import annotations

import os
import json
import subprocess
import sys
from contextlib import closing
from pathlib import Path

try:
    from flask import Flask, jsonify, render_template, request
except ImportError:  # pragma: no cover - exercised only when Flask is absent.
    Flask = None
    jsonify = None
    render_template = None
    request = None

from .db import connect_db, resolve_db_path, utcnow_iso
from .query import (
    build_agent_stats_payload,
    build_board_payload,
    build_gantt_payload,
    build_health_payload,
    build_integration_queue_payload,
    build_task_detail_payload,
    build_task_timeline_payload,
    build_task_communications_payload,
    build_daily_metrics_payload,
    build_task_aggregate_payload,
)

WORKSPACE_ROOT = Path(__file__).resolve().parent.parent
DEFAULT_TASKS_ROOT = WORKSPACE_ROOT / 'tasks'
DEFAULT_CONFIG_PATH = WORKSPACE_ROOT / 'config.json'


def create_app(db_path: str | None = None, *, tasks_root: str | None = None, control_config_path: str | None = None):
    if Flask is None or jsonify is None or render_template is None or request is None:
        raise RuntimeError('Flask is not installed. Install dependencies from dashboard/requirements.txt first.')

    resolved_db_path = str(resolve_db_path(db_path))
    app = Flask(
        __name__,
        template_folder='templates',
        static_folder='static',
        static_url_path='/static',
    )
    app.config['TASK_BOARD_DB_PATH'] = resolved_db_path
    app.config['TASKS_ROOT'] = str(Path(tasks_root).expanduser().resolve()) if tasks_root else str(DEFAULT_TASKS_ROOT)
    app.config['TASK_CONTROL_CONFIG_PATH'] = str(Path(control_config_path).expanduser().resolve()) if control_config_path else str(DEFAULT_CONFIG_PATH)

    # Initialize the schema once at startup. Request handlers should use
    # read-only style connections that do not rewrite metadata on every GET.
    with closing(connect_db(resolved_db_path, initialize=True)):
        pass

    def _with_connection(callback):
        with closing(connect_db(app.config['TASK_BOARD_DB_PATH'], initialize=False)) as conn:
            return callback(conn)

    def _run_control_script(script_name: str, *args: str):
        script_path = WORKSPACE_ROOT / 'scripts' / script_name
        completed = subprocess.run(
            [sys.executable, str(script_path), *args],
            cwd=str(WORKSPACE_ROOT),
            capture_output=True,
            text=True,
            check=True,
        )
        return json.loads(completed.stdout)

    def _pool_detail(task_id: str):
        try:
            payload = _run_control_script(
                'task-pool-view.py',
                '--json',
                '--explain',
                task_id,
                '--tasks-root',
                app.config['TASKS_ROOT'],
                '--config',
                app.config['TASK_CONTROL_CONFIG_PATH'],
            )
        except (subprocess.CalledProcessError, json.JSONDecodeError):
            return None
        if isinstance(payload, list) and payload:
            return payload[0]
        return None

    def _board_payload():
        return _with_connection(
            lambda conn: build_board_payload(
                conn,
                project=request.args.get('project'),
                agent=request.args.get('agent'),
            )
        )

    def _gantt_payload():
        return _with_connection(
            lambda conn: build_gantt_payload(
                conn,
                project=request.args.get('project'),
                agent=request.args.get('agent'),
            )
        )

    def _agents_payload():
        return _with_connection(
            lambda conn: build_agent_stats_payload(
                conn,
                project=request.args.get('project'),
            )
        )

    def _integration_queue_payload():
        return _with_connection(
            lambda conn: build_integration_queue_payload(
                conn,
                project=request.args.get('project'),
                agent=request.args.get('agent'),
            )
        )

    @app.get('/')
    def index():
        return render_template('index.html')

    @app.get('/api/health')
    def api_health():
        payload = _with_connection(
            lambda conn: build_health_payload(conn, db_path=app.config['TASK_BOARD_DB_PATH'])
        )
        return jsonify(payload)

    @app.get('/api/board')
    def api_board():
        return jsonify(_board_payload())

    @app.get('/api/gantt')
    def api_gantt():
        return jsonify(_gantt_payload())

    @app.get('/api/agents')
    def api_agents():
        return jsonify(_agents_payload())

    @app.get('/api/integration-queue')
    def api_integration_queue():
        return jsonify(_integration_queue_payload())

    @app.get('/api/tasks')
    def api_tasks_compat():
        payload = _board_payload()
        tasks = []
        for column in payload.get('columns', []):
            for task in column.get('tasks', []):
                compat_task = dict(task)
                compat_task['status'] = task.get('board_status') or task.get('current_status')
                compat_task['review_at'] = task.get('review_completed_at')
                compat_task['verify_at'] = task.get('verify_completed_at')
                tasks.append(compat_task)
        return jsonify(tasks)

    @app.get('/api/pool')
    def api_pool():
        payload = _run_control_script(
            'task-pool-view.py',
            '--summary-json',
            '--tasks-root',
            app.config['TASKS_ROOT'],
            '--config',
            app.config['TASK_CONTROL_CONFIG_PATH'],
        )
        return jsonify({
            'generated_at': utcnow_iso(),
            'summary': payload.get('summary') or {},
            'items': payload.get('items') or [],
        })

    @app.get('/api/pm-inbox')
    def api_pm_inbox():
        payload = _run_control_script(
            'task-inbox.py',
            '--json',
            '--tasks-root',
            app.config['TASKS_ROOT'],
            '--control-config',
            app.config['TASK_CONTROL_CONFIG_PATH'],
        )
        return jsonify({
            'generated_at': utcnow_iso(),
            'items': payload,
        })

    @app.get('/api/tasks/gantt')
    def api_tasks_gantt_compat():
        payload = _gantt_payload()
        items = []
        for item in payload.get('items', []):
            milestones = item.get('milestones', {})
            items.append({
                'task_id': item.get('task_id'),
                'title': item.get('title'),
                'project': item.get('project'),
                'assigned_agent': item.get('assigned_agent'),
                'status': item.get('board_status') or item.get('current_status'),
                'created_at': milestones.get('created'),
                'dispatched_at': milestones.get('dispatched'),
                'ack_at': milestones.get('ack'),
                'completed_at': milestones.get('completed'),
                'review_at': milestones.get('review_completed'),
                'verify_at': milestones.get('verify_completed'),
                'current_status_at': milestones.get('current_status'),
            })
        return jsonify(items)


    @app.get('/api/tasks/aggregate')
    def api_tasks_aggregate():
        payload = _with_connection(
            lambda conn: build_task_aggregate_payload(
                conn,
                project=request.args.get('project'),
                owner_pm=request.args.get('owner_pm'),
                domain=request.args.get('domain'),
                task_level=request.args.get('task_level'),
                parent_task_id=request.args.get('parent_task_id'),
                root_request_id=request.args.get('root_request_id'),
            )
        )
        return jsonify(payload)

    @app.get('/api/tasks/<task_id>/detail')
    def api_task_detail(task_id: str):
        payload = _with_connection(
            lambda conn: build_task_detail_payload(conn, task_id)
        )
        if payload.get('task') is None:
            return jsonify({'error': 'task not found', 'task_id': task_id}), 404
        if (payload.get('task') or {}).get('current_status') == 'pooled':
            payload['pool_status'] = _pool_detail(task_id)
        return jsonify(payload)


    @app.get('/api/tasks/<task_id>/timeline')
    def api_task_timeline(task_id: str):
        payload = _with_connection(
            lambda conn: build_task_timeline_payload(conn, task_id)
        )
        if payload.get('task') is None:
            return jsonify({'error': 'task not found', 'task_id': task_id}), 404
        return jsonify(payload)

    @app.get('/api/tasks/<task_id>/communications')
    def api_task_communications(task_id: str):
        payload = _with_connection(
            lambda conn: build_task_communications_payload(conn, task_id)
        )
        if payload.get('task') is None:
            return jsonify({'error': 'task not found', 'task_id': task_id}), 404
        return jsonify(payload)


    @app.get('/api/metrics/daily')
    def api_metrics_daily():
        payload = _with_connection(
            lambda conn: build_daily_metrics_payload(
                conn,
                project=request.args.get('project'),
                start_date=request.args.get('start_date'),
                end_date=request.args.get('end_date'),
            )
        )
        return jsonify(payload)

    @app.get('/api/agents/stats')
    def api_agents_stats_compat():
        payload = _agents_payload()
        agents = []
        for agent_payload in payload.get('agents', []):
            compat_agent = dict(agent_payload)
            compat_agent['completed_count'] = agent_payload.get('completed_task_count', 0)
            compat_agent['active_count'] = agent_payload.get('active_task_count', 0)
            compat_agent['total_work_seconds'] = agent_payload.get('total_tracked_work_seconds', 0)
            agents.append(compat_agent)
        return jsonify(agents)

    return app


if __name__ == '__main__':
    app = create_app(os.getenv('TASK_BOARD_DB_PATH'))
    app.run(host=os.getenv('TASK_BOARD_HOST', '127.0.0.1'), port=int(os.getenv('TASK_BOARD_PORT', '5001')), debug=False)
