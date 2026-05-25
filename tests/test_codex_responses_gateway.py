from __future__ import annotations

import http.client
import json
import os
import subprocess
import sys
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[1]
GATEWAY = REPO_ROOT / 'scripts' / 'codex-responses-gateway.py'
INSTALL_PROFILE = REPO_ROOT / 'scripts' / 'install-codex-gateway-profile.py'
TEAMCTL = REPO_ROOT / 'scripts' / 'teamctl.sh'
RENDER_CONFIG = REPO_ROOT / 'scripts' / 'render-local-config.py'
EXAMPLE_CONFIG = REPO_ROOT / 'config' / 'codex-responses-gateway.example.json'


def _free_port() -> int:
    import socket
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
        sock.bind(('127.0.0.1', 0))
        return int(sock.getsockname()[1])


class _StubHandler(BaseHTTPRequestHandler):
    status = 200
    content_type = 'application/json'
    body = b'{"id":"resp_test","object":"response"}'
    seen: list[dict] = []

    def log_message(self, fmt: str, *args):
        return

    def do_POST(self):  # noqa: N802
        length = int(self.headers.get('Content-Length', '0'))
        raw = self.rfile.read(length)
        self.__class__.seen.append({
            'path': self.path,
            'authorization': self.headers.get('Authorization'),
            'body': json.loads(raw.decode('utf-8')),
        })
        self.send_response(self.__class__.status)
        self.send_header('Content-Type', self.__class__.content_type)
        self.send_header('Content-Length', str(len(self.__class__.body)))
        self.end_headers()
        self.wfile.write(self.__class__.body)


def _start_stub(status=200, body=b'{"id":"resp_test","object":"response"}', content_type='application/json'):
    handler = type('StubHandler', (_StubHandler,), {'status': status, 'body': body, 'content_type': content_type, 'seen': []})
    server = ThreadingHTTPServer(('127.0.0.1', 0), handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    return server, handler


def _request(port: int, path: str, payload: dict, token='local-token'):
    conn = http.client.HTTPConnection('127.0.0.1', port, timeout=5)
    headers = {'Content-Type': 'application/json', 'Authorization': f'Bearer {token}'}
    conn.request('POST', path, body=json.dumps(payload).encode('utf-8'), headers=headers)
    response = conn.getresponse()
    body = response.read()
    conn.close()
    return response.status, dict(response.getheaders()), body


def _gateway_config(tmp_path: Path, upstream_url: str) -> Path:
    path = tmp_path / 'gateway.json'
    path.write_text(json.dumps({
        'auth': {'bearer_token_env': 'CODEX_GATEWAY_API_KEY'},
        'routing': {'max_failovers': 0, 'retry_statuses': [429, 500, 502, 503, 504]},
        'upstreams': [{
            'id': 'stub',
            'base_url': upstream_url,
            'api_key_env': 'UPSTREAM_KEY',
            'model_map': {'gpt-5.4': 'upstream-model'},
        }],
    }), encoding='utf-8')
    return path


def test_gateway_forwards_responses_request_and_maps_model(tmp_path, monkeypatch):
    stub, handler = _start_stub()
    try:
        cfg = _gateway_config(tmp_path, f'http://127.0.0.1:{stub.server_port}/v1')
        monkeypatch.setenv('CODEX_GATEWAY_API_KEY', 'local-token')
        monkeypatch.setenv('UPSTREAM_KEY', 'upstream-token')
        mod_globals = {}
        exec(GATEWAY.read_text(encoding='utf-8'), mod_globals)
        config = mod_globals['load_config'](cfg)
        server_cls = mod_globals['GatewayServer']
        gateway = server_cls(('127.0.0.1', 0), config, quiet=True)
        thread = threading.Thread(target=gateway.serve_forever, daemon=True)
        thread.start()
        try:
            status, headers, body = _request(gateway.server_port, '/v1/responses', {'model': 'gpt-5.4', 'input': 'hi'})
        finally:
            gateway.shutdown()
            gateway.server_close()
        assert status == 200
        assert headers['X-Codex-Gateway-Upstream'] == 'stub'
        assert json.loads(body.decode('utf-8'))['id'] == 'resp_test'
        assert handler.seen[0]['path'] == '/v1/responses'
        assert handler.seen[0]['authorization'] == 'Bearer upstream-token'
        assert handler.seen[0]['body']['model'] == 'upstream-model'
    finally:
        stub.shutdown()
        stub.server_close()


def test_gateway_rejects_missing_bearer_token(tmp_path, monkeypatch):
    stub, _ = _start_stub()
    try:
        cfg = _gateway_config(tmp_path, f'http://127.0.0.1:{stub.server_port}/v1')
        monkeypatch.setenv('CODEX_GATEWAY_API_KEY', 'local-token')
        mod_globals = {}
        exec(GATEWAY.read_text(encoding='utf-8'), mod_globals)
        gateway = mod_globals['GatewayServer'](('127.0.0.1', 0), mod_globals['load_config'](cfg), quiet=True)
        thread = threading.Thread(target=gateway.serve_forever, daemon=True)
        thread.start()
        try:
            status, _, body = _request(gateway.server_port, '/v1/responses', {'model': 'gpt-5.4'}, token='wrong')
        finally:
            gateway.shutdown()
            gateway.server_close()
        assert status == 401
        assert json.loads(body.decode('utf-8'))['error'] == 'unauthorized'
    finally:
        stub.shutdown()
        stub.server_close()


def test_profile_installer_renders_managed_block(tmp_path):
    codex_config = tmp_path / 'config.toml'
    completed = subprocess.run([
        sys.executable,
        str(INSTALL_PROFILE),
        '--codex-config', str(codex_config),
        '--gateway-base-url', 'http://127.0.0.1:8787/v1',
        '--dry-run',
    ], cwd=str(REPO_ROOT), capture_output=True, text=True, check=True)
    assert '[model_providers.codex-gateway]' in completed.stdout
    assert 'wire_api = "responses"' in completed.stdout
    assert 'requires_openai_auth = false' in completed.stdout
    assert '[profiles.dev-team]' in completed.stdout


def test_gateway_config_example_is_valid():
    completed = subprocess.run([
        sys.executable,
        str(GATEWAY),
        'check-config', '--config', str(EXAMPLE_CONFIG),
    ], cwd=str(REPO_ROOT), capture_output=True, text=True, check=True)
    payload = json.loads(completed.stdout)
    assert payload['ok'] is True
    assert payload['upstreams'] == ['openai-primary']


def test_teamctl_shell_syntax_includes_gateway_commands():
    subprocess.run(['bash', '-n', str(TEAMCTL)], cwd=str(REPO_ROOT), check=True)
    content = TEAMCTL.read_text(encoding='utf-8')
    assert 'start-codex-gateway' in content
    assert 'install-codex-profile' in content
    assert 'sessions)' in content
    assert 'attach)' in content
    assert '--team <size>' in content


def _render_team_profile(tmp_path: Path, team_size: str) -> dict:
    completed = subprocess.run([
        sys.executable,
        str(RENDER_CONFIG),
        '--input', str(REPO_ROOT / 'config.json'),
        '--workspace-root', str(tmp_path / 'workspace'),
        '--team-size', team_size,
        '--dry-run',
    ], cwd=str(REPO_ROOT), capture_output=True, text=True, check=True)
    return json.loads(completed.stdout)


def test_render_local_config_team_profiles(tmp_path):
    small = _render_team_profile(tmp_path, 'small')
    assert small['team_profile'] == 'small'
    assert list(small['agents']) == ['pm-chief', 'arch-1', 'dev-1', 'qa-1']
    assert small['domain_policies']['development']['default_reviewer'] == 'arch-1'
    assert small['domain_policies']['development']['default_tester'] == 'qa-1'

    medium = _render_team_profile(tmp_path, 'medium')
    assert medium['team_profile'] == 'medium'
    assert len(medium['agents']) == 7
    assert {'dev-3', 'review-1'}.issubset(medium['agents'])
    assert medium['domain_policies']['development']['default_reviewer'] == 'review-1'

    large = _render_team_profile(tmp_path, 'large')
    assert large['team_profile'] == 'large'
    assert len(large['agents']) == 13
    assert {'arch-2', 'dev-6', 'qa-2', 'review-2'}.issubset(large['agents'])
    assert large['orchestration']['domains']['development'] == [
        'dev-1', 'dev-2', 'dev-3', 'dev-4', 'dev-5', 'dev-6'
    ]
