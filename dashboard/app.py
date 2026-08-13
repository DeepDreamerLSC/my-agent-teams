from __future__ import annotations

import os
import json
import sqlite3
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
from control_plane.bootstrap import bootstrap_project, check_bootstrap, uninstall_project
from control_plane.backends.registry import BackendRegistry
from control_plane.errors import ControlPlaneError
from control_plane.service import ControlPlaneService

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

    # Existing config projects are imported conservatively into the control
    # plane. Missing or non-Git roots remain skipped/unknown; no project is
    # reported online merely because it appears in config.json.
    try:
        legacy_config = json.loads(Path(app.config['TASK_CONTROL_CONFIG_PATH']).read_text(encoding='utf-8'))
        with closing(connect_db(resolved_db_path, initialize=False)) as conn:
            with conn:
                ControlPlaneService(conn).import_legacy_projects(legacy_config, actor='dashboard_startup')
    except (OSError, json.JSONDecodeError, ControlPlaneError):
        pass

    def _with_connection(callback):
        with closing(connect_db(app.config['TASK_BOARD_DB_PATH'], initialize=False)) as conn:
            return callback(conn)

    def _control_plane_call(callback, *, success_status=200):
        try:
            with closing(connect_db(app.config['TASK_BOARD_DB_PATH'], initialize=False)) as conn:
                with conn:
                    payload = callback(ControlPlaneService(conn))
            return jsonify(payload), success_status
        except ControlPlaneError as exc:
            return jsonify({'error': {'code': exc.code, 'message': str(exc)}}), 400
        except sqlite3.IntegrityError as exc:
            return jsonify({'error': {'code': 'integrity_error', 'message': str(exc)}}), 409

    def _json_body():
        payload = request.get_json(silent=True)
        return payload if isinstance(payload, dict) else {}

    def _check_event_token():
        expected = os.getenv('MY_AGENT_TEAMS_CONTROL_PLANE_TOKEN', '').strip()
        if not expected:
            return None
        authorization = request.headers.get('Authorization', '')
        if authorization != f'Bearer {expected}':
            return jsonify({'error': {'code': 'unauthorized', 'message': 'control-plane event token is invalid'}}), 401
        return None

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

    # Cross-project control-plane API. These endpoints only expose metadata,
    # summaries, and artifact references; they never read full transcripts.
    @app.get('/api/control-plane/overview')
    def api_control_plane_overview():
        return _control_plane_call(
            lambda service: service.overview(project_id=request.args.get('project'))
        )

    @app.get('/api/control-plane/projects')
    def api_control_plane_projects():
        return _control_plane_call(
            lambda service: service.list_projects(status=request.args.get('status'))
        )

    @app.post('/api/control-plane/projects')
    def api_control_plane_register_project():
        body = _json_body()
        metadata = body.get('metadata') if isinstance(body.get('metadata'), dict) else {}
        if body.get('allowed_roots'):
            metadata['allowed_roots'] = body['allowed_roots']
        return _control_plane_call(
            lambda service: service.register_project(
                project_id=str(body.get('project_id') or ''),
                name=str(body.get('name') or body.get('project_id') or ''),
                repo_root=str(body.get('repo_root') or ''),
                prod_root=body.get('prod_root'),
                default_branch=str(body.get('default_branch') or 'main'),
                control_plane_url=body.get('control_plane_url'),
                capabilities=body.get('capabilities') if isinstance(body.get('capabilities'), dict) else {},
                metadata=metadata,
                status=str(body.get('status') or 'active'),
                actor=str(body.get('actor') or 'api'),
                source='dashboard_api',
            ),
            success_status=201,
        )

    @app.get('/api/control-plane/projects/<project_id>/check')
    def api_control_plane_check_project(project_id: str):
        return _control_plane_call(lambda service: service.check_project(project_id))

    @app.post('/api/control-plane/projects/<project_id>/scope-check')
    def api_control_plane_scope_check(project_id: str):
        body = _json_body()
        paths = body.get('paths') if isinstance(body.get('paths'), list) else []
        return _control_plane_call(
            lambda service: service.validate_write_scope(
                project_id, [str(path) for path in paths], environment=str(body.get('environment') or 'dev')
            )
        )

    @app.get('/api/control-plane/projects/<project_id>/bootstrap-check')
    def api_control_plane_bootstrap_check(project_id: str):
        def check(_service):
            project = _service.get_project(project_id)
            return check_bootstrap(repo_root=project['repo_root'])
        return _control_plane_call(check)

    @app.get('/api/control-plane/requirements')
    def api_control_plane_requirements():
        return _control_plane_call(
            lambda service: service.list_requirements(
                project_id=request.args.get('project'), status=request.args.get('status')
            )
        )

    @app.post('/api/control-plane/requirements')
    def api_control_plane_create_requirement():
        body = _json_body()
        return _control_plane_call(
            lambda service: service.create_requirement(
                project_id=str(body.get('project_id') or ''),
                title=str(body.get('title') or ''),
                description=str(body.get('description') or ''),
                acceptance=body.get('acceptance') if isinstance(body.get('acceptance'), list) else [],
                priority=str(body.get('priority') or 'medium'),
                owner_id=body.get('owner_id'),
                requirement_id=body.get('requirement_id'),
                actor=str(body.get('actor') or 'api'),
            ),
            success_status=201,
        )

    @app.get('/api/control-plane/sessions')
    def api_control_plane_sessions():
        return _control_plane_call(
            lambda service: service.list_sessions(
                project_id=request.args.get('project'),
                requirement_id=request.args.get('requirement'),
                task_id=request.args.get('task'),
            )
        )

    @app.post('/api/control-plane/sessions')
    def api_control_plane_register_session():
        body = _json_body()
        return _control_plane_call(
            lambda service: service.register_session(
                project_id=str(body.get('project_id') or ''),
                session_id=body.get('session_id'),
                requirement_id=body.get('requirement_id'),
                task_id=body.get('task_id'),
                thread_id=body.get('thread_id'),
                parent_thread_id=body.get('parent_thread_id'),
                role=str(body.get('role') or ''),
                execution_backend=str(body.get('execution_backend') or ''),
                cwd=body.get('cwd'),
                environment=body.get('environment'),
                worktree=body.get('worktree'),
                branch=body.get('branch'),
                session_status=str(body.get('session_status') or 'unknown'),
                current_gate=body.get('current_gate'),
                capabilities=body.get('capabilities') if isinstance(body.get('capabilities'), dict) else {},
                external_ref=body.get('external_ref'),
                actor=str(body.get('actor') or 'api'),
            ),
            success_status=201,
        )

    @app.post('/api/control-plane/sessions/create')
    def api_control_plane_create_session():
        body = _json_body()
        try:
            backend = BackendRegistry().get(str(body.get('execution_backend') or ''))
        except KeyError as exc:
            return jsonify({'error': {'code': 'unsupported_backend', 'message': str(exc)}}), 400
        return _control_plane_call(
            lambda service: service.create_session(
                project_id=str(body.get('project_id') or ''),
                requirement_id=body.get('requirement_id'),
                task_id=body.get('task_id'),
                role=str(body.get('role') or ''),
                execution_backend=backend,
                parent_thread_id=body.get('parent_thread_id'),
                cwd=body.get('cwd'),
                environment=body.get('environment'),
                worktree=body.get('worktree'),
                branch=body.get('branch'),
                actor=str(body.get('actor') or 'pm'),
            ),
            success_status=201,
        )

    @app.post('/api/control-plane/sessions/<session_id>/bind')
    def api_control_plane_bind_session(session_id: str):
        body = _json_body()
        return _control_plane_call(
            lambda service: service.bind_session(
                session_id,
                requirement_id=body.get('requirement_id'),
                task_id=body.get('task_id'),
                actor=str(body.get('actor') or 'api'),
            )
        )

    @app.get('/api/control-plane/sessions/<session_id>/events')
    def api_control_plane_session_events(session_id: str):
        return _control_plane_call(lambda service: service.list_session_events(session_id))

    @app.post('/api/control-plane/sessions/<session_id>/heartbeat')
    def api_control_plane_heartbeat(session_id: str):
        body = _json_body()
        return _control_plane_call(
            lambda service: service.heartbeat(
                session_id,
                idempotency_key=str(body.get('idempotency_key') or ''),
                sequence=body.get('sequence'),
                status=body.get('status'),
                capabilities=body.get('capabilities') if isinstance(body.get('capabilities'), dict) else {},
                source=str(body.get('source') or 'dashboard_api'),
            )
        )

    @app.post('/api/control-plane/events')
    def api_control_plane_event():
        denied = _check_event_token()
        if denied:
            return denied
        body = _json_body()
        return _control_plane_call(
            lambda service: service.record_session_event(
                session_id=str(body.get('session_id') or ''),
                event_type=str(body.get('event_type') or ''),
                idempotency_key=str(body.get('idempotency_key') or ''),
                project_id=body.get('project_id'),
                event_id=body.get('event_id'),
                event_at=body.get('event_at'),
                sequence=body.get('sequence'),
                status=body.get('status'),
                current_gate=body.get('current_gate'),
                last_error=body.get('last_error'),
                payload=body.get('payload') if isinstance(body.get('payload'), dict) else {},
                source=str(body.get('source') or 'dashboard_api'),
                actor=str(body.get('actor') or 'system'),
            )
        )

    @app.get('/api/control-plane/requirements/<requirement_id>/gates')
    def api_control_plane_gates(requirement_id: str):
        return _control_plane_call(lambda service: service.list_gates(requirement_id))

    @app.get('/api/control-plane/requirements/<requirement_id>/timeline')
    def api_control_plane_requirement_timeline(requirement_id: str):
        return _control_plane_call(lambda service: service.requirement_timeline(requirement_id))

    @app.post('/api/control-plane/gates')
    def api_control_plane_decide_gate():
        body = _json_body()
        return _control_plane_call(
            lambda service: service.decide_gate(
                requirement_id=str(body.get('requirement_id') or ''),
                stage=str(body.get('stage') or ''),
                status=str(body.get('status') or ''),
                actor=str(body.get('actor') or ''),
                output=body.get('output') if isinstance(body.get('output'), dict) else {},
                rejection_reason=body.get('rejection_reason'),
                task_id=body.get('task_id'),
                round_number=body.get('round'),
            )
        )

    @app.post('/api/control-plane/workflow/advance')
    def api_control_plane_advance_workflow():
        body = _json_body()
        return _control_plane_call(
            lambda service: service.advance_workflow(
                str(body.get('requirement_id') or ''),
                actor=str(body.get('actor') or 'pm'),
                task_id=body.get('task_id'),
            )
        )

    @app.get('/api/control-plane/owner-decisions')
    def api_control_plane_owner_decisions():
        return _control_plane_call(
            lambda service: service.list_owner_decisions(
                status=request.args.get('status', 'open'), project_id=request.args.get('project')
            )
        )

    @app.post('/api/control-plane/owner-decisions')
    def api_control_plane_open_owner_decision():
        body = _json_body()
        return _control_plane_call(
            lambda service: service.create_owner_decision(
                project_id=str(body.get('project_id') or ''),
                category=str(body.get('category') or ''),
                summary=str(body.get('summary') or ''),
                options=body.get('options') if isinstance(body.get('options'), list) else [],
                impact=str(body.get('impact') or ''),
                recommendation=str(body.get('recommendation') or ''),
                due_at=body.get('due_at'),
                requirement_id=body.get('requirement_id'),
                task_id=body.get('task_id'),
                actor=str(body.get('actor') or 'pm'),
            ),
            success_status=201,
        )

    @app.post('/api/control-plane/owner-decisions/<decision_id>/resolve')
    def api_control_plane_resolve_owner_decision(decision_id: str):
        body = _json_body()
        return _control_plane_call(
            lambda service: service.resolve_owner_decision(
                decision_id,
                decision=body.get('decision') if isinstance(body.get('decision'), dict) else {},
                actor=str(body.get('actor') or 'owner'),
            )
        )

    @app.post('/api/control-plane/artifacts')
    def api_control_plane_artifact():
        body = _json_body()
        return _control_plane_call(
            lambda service: service.attach_artifact(
                project_id=str(body.get('project_id') or ''),
                requirement_id=body.get('requirement_id'),
                task_id=body.get('task_id'),
                session_id=body.get('session_id'),
                environment=str(body.get('environment') or 'dev'),
                kind=str(body.get('kind') or ''),
                uri=str(body.get('uri') or ''),
                checksum=body.get('checksum'),
                summary=str(body.get('summary') or ''),
                metadata=body.get('metadata') if isinstance(body.get('metadata'), dict) else {},
                actor=str(body.get('actor') or 'system'),
            ),
            success_status=201,
        )

    return app


if __name__ == '__main__':
    app = create_app(os.getenv('TASK_BOARD_DB_PATH'))
    app.run(host=os.getenv('TASK_BOARD_HOST', '127.0.0.1'), port=int(os.getenv('TASK_BOARD_PORT', '5001')), debug=False)
