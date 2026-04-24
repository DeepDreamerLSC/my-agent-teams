from __future__ import annotations

import os
from contextlib import closing

try:
    from flask import Flask, jsonify, request
except ImportError:  # pragma: no cover - exercised only when Flask is absent.
    Flask = None
    jsonify = None
    request = None

from .db import connect_db, resolve_db_path
from .query import (
    build_agent_stats_payload,
    build_board_payload,
    build_gantt_payload,
    build_health_payload,
)


def create_app(db_path: str | None = None):
    if Flask is None or jsonify is None or request is None:
        raise RuntimeError('Flask is not installed. Install dependencies from dashboard/requirements.txt first.')

    resolved_db_path = str(resolve_db_path(db_path))
    app = Flask(__name__)
    app.config['TASK_BOARD_DB_PATH'] = resolved_db_path

    def _with_connection(callback):
        with closing(connect_db(app.config['TASK_BOARD_DB_PATH'])) as conn:
            return callback(conn)

    @app.get('/')
    def index():
        return jsonify({
            'service': 'task-board-api',
            'db_path': app.config['TASK_BOARD_DB_PATH'],
            'routes': ['/api/health', '/api/board', '/api/gantt', '/api/agents'],
        })

    @app.get('/api/health')
    def api_health():
        payload = _with_connection(
            lambda conn: build_health_payload(conn, db_path=app.config['TASK_BOARD_DB_PATH'])
        )
        return jsonify(payload)

    @app.get('/api/board')
    def api_board():
        payload = _with_connection(
            lambda conn: build_board_payload(
                conn,
                project=request.args.get('project'),
                agent=request.args.get('agent'),
            )
        )
        return jsonify(payload)

    @app.get('/api/gantt')
    def api_gantt():
        payload = _with_connection(
            lambda conn: build_gantt_payload(
                conn,
                project=request.args.get('project'),
                agent=request.args.get('agent'),
            )
        )
        return jsonify(payload)

    @app.get('/api/agents')
    def api_agents():
        payload = _with_connection(
            lambda conn: build_agent_stats_payload(
                conn,
                project=request.args.get('project'),
            )
        )
        return jsonify(payload)

    return app


if __name__ == '__main__':
    app = create_app(os.getenv('TASK_BOARD_DB_PATH'))
    app.run(host=os.getenv('TASK_BOARD_HOST', '127.0.0.1'), port=int(os.getenv('TASK_BOARD_PORT', '5001')), debug=False)
