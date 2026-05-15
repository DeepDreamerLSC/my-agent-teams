#!/usr/bin/env python3
"""Small OpenAI Responses API gateway for Codex agents.

The gateway intentionally implements only the Codex-facing Responses path:
POST /v1/responses. It forwards the request to one of the configured upstreams,
keeps streaming responses as a raw pass-through, and only retries/fails over
before any response bytes are sent to the Codex client.
"""
from __future__ import annotations

import argparse
import json
import os
import socket
import sys
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Any

HOP_BY_HOP_HEADERS = {
    "connection",
    "keep-alive",
    "proxy-authenticate",
    "proxy-authorization",
    "te",
    "trailer",
    "transfer-encoding",
    "upgrade",
}
DEFAULT_RETRY_STATUSES = {429, 500, 502, 503, 504}
RESPONSES_PATHS = {"/responses", "/v1/responses"}
HEALTH_PATHS = {"/health", "/v1/health"}


@dataclass(frozen=True)
class Upstream:
    id: str
    base_url: str
    api_key: str | None
    timeout_seconds: float
    model_map: dict[str, str]
    headers: dict[str, str]
    enabled: bool = True

    @property
    def responses_url(self) -> str:
        base = self.base_url.rstrip("/")
        if base.endswith("/responses"):
            return base
        return f"{base}/responses"


@dataclass(frozen=True)
class GatewayConfig:
    auth_token: str | None
    retry_statuses: set[int]
    max_failovers: int
    max_body_bytes: int
    upstreams: list[Upstream]


def _resolve_secret(payload: dict[str, Any], *, env_key_name: str, inline_key_name: str) -> str | None:
    inline = payload.get(inline_key_name)
    if inline:
        return str(inline)
    env_name = payload.get(env_key_name)
    if env_name:
        return os.environ.get(str(env_name))
    return None


def load_config(path: str | Path) -> GatewayConfig:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    auth = data.get("auth") or {}
    routing = data.get("routing") or {}
    retry_statuses = {int(item) for item in routing.get("retry_statuses", sorted(DEFAULT_RETRY_STATUSES))}
    max_failovers = int(routing.get("max_failovers", 1))
    max_body_bytes = int(data.get("max_body_bytes", 25 * 1024 * 1024))

    upstreams: list[Upstream] = []
    for index, item in enumerate(data.get("upstreams") or []):
        if not item or item.get("enabled", True) is False:
            continue
        base_url = str(item.get("base_url") or "").strip()
        if not base_url:
            raise ValueError(f"upstreams[{index}].base_url is required")
        model_map_raw = item.get("model_map") or item.get("models") or {}
        if not isinstance(model_map_raw, dict):
            raise ValueError(f"upstreams[{index}].model_map must be an object")
        headers_raw = item.get("headers") or {}
        if not isinstance(headers_raw, dict):
            raise ValueError(f"upstreams[{index}].headers must be an object")
        upstreams.append(
            Upstream(
                id=str(item.get("id") or f"upstream-{index + 1}"),
                base_url=base_url,
                api_key=_resolve_secret(item, env_key_name="api_key_env", inline_key_name="api_key"),
                timeout_seconds=float(item.get("timeout_seconds", data.get("timeout_seconds", 600))),
                model_map={str(k): str(v) for k, v in model_map_raw.items()},
                headers={str(k): str(v) for k, v in headers_raw.items()},
            )
        )
    if not upstreams:
        raise ValueError("at least one enabled upstream is required")

    return GatewayConfig(
        auth_token=_resolve_secret(auth, env_key_name="bearer_token_env", inline_key_name="bearer_token"),
        retry_statuses=retry_statuses,
        max_failovers=max_failovers,
        max_body_bytes=max_body_bytes,
        upstreams=upstreams,
    )


def _json_bytes(payload: dict[str, Any]) -> bytes:
    return json.dumps(payload, ensure_ascii=False, separators=(",", ":")).encode("utf-8")


def _is_retryable_status(status: int, config: GatewayConfig, attempts: int) -> bool:
    return status in config.retry_statuses and attempts <= config.max_failovers


def _response_headers_from_upstream(response: Any, *, body_length: int | None = None, upstream_id: str) -> list[tuple[str, str]]:
    headers: list[tuple[str, str]] = []
    for key, value in response.headers.items():
        lower = key.lower()
        if lower in HOP_BY_HOP_HEADERS or lower in {"content-length", "server", "date"}:
            continue
        headers.append((key, value))
    headers.append(("X-Codex-Gateway-Upstream", upstream_id))
    if body_length is not None:
        headers.append(("Content-Length", str(body_length)))
    else:
        headers.append(("Connection", "close"))
    return headers


def build_upstream_request(
    upstream: Upstream,
    payload: dict[str, Any],
    incoming_headers: Any,
) -> urllib.request.Request:
    forwarded_payload = dict(payload)
    model = forwarded_payload.get("model")
    if isinstance(model, str) and model in upstream.model_map:
        forwarded_payload["model"] = upstream.model_map[model]
    headers = {
        "Content-Type": "application/json",
        "Accept": incoming_headers.get("Accept", "application/json"),
        "User-Agent": "my-agent-teams-codex-responses-gateway/1.0",
    }
    if upstream.api_key:
        headers["Authorization"] = f"Bearer {upstream.api_key}"
    headers.update(upstream.headers)
    return urllib.request.Request(
        upstream.responses_url,
        data=_json_bytes(forwarded_payload),
        headers=headers,
        method="POST",
    )


class GatewayHandler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"
    server_version = "CodexResponsesGateway/1.0"

    @property
    def gateway_config(self) -> GatewayConfig:
        return self.server.gateway_config  # type: ignore[attr-defined]

    def log_message(self, fmt: str, *args: Any) -> None:  # pragma: no cover - exercised through runtime logs
        if getattr(self.server, "quiet", False):  # type: ignore[attr-defined]
            return
        super().log_message(fmt, *args)

    def do_GET(self) -> None:  # noqa: N802 - http.server API
        if self.path.split("?", 1)[0] not in HEALTH_PATHS:
            self._send_json(404, {"error": "not_found"})
            return
        cfg = self.gateway_config
        self._send_json(
            200,
            {
                "status": "ok",
                "upstreams": [item.id for item in cfg.upstreams],
                "auth_required": bool(cfg.auth_token),
                "retry_statuses": sorted(cfg.retry_statuses),
                "max_failovers": cfg.max_failovers,
            },
        )

    def do_POST(self) -> None:  # noqa: N802 - http.server API
        if self.path.split("?", 1)[0] not in RESPONSES_PATHS:
            self._send_json(404, {"error": "not_found"})
            return
        if not self._authorize():
            return
        payload = self._read_payload()
        if payload is None:
            return
        self._proxy_responses(payload)

    def _authorize(self) -> bool:
        expected = self.gateway_config.auth_token
        if not expected:
            return True
        actual = self.headers.get("Authorization", "")
        if actual != f"Bearer {expected}":
            self._send_json(401, {"error": "unauthorized"}, headers={"WWW-Authenticate": "Bearer"})
            return False
        return True

    def _read_payload(self) -> dict[str, Any] | None:
        try:
            length = int(self.headers.get("Content-Length", "0"))
        except ValueError:
            self._send_json(400, {"error": "invalid_content_length"})
            return None
        if length <= 0:
            self._send_json(400, {"error": "empty_body"})
            return None
        if length > self.gateway_config.max_body_bytes:
            self._send_json(413, {"error": "body_too_large"})
            return None
        raw = self.rfile.read(length)
        try:
            payload = json.loads(raw.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            self._send_json(400, {"error": "invalid_json"})
            return None
        if not isinstance(payload, dict):
            self._send_json(400, {"error": "request_must_be_object"})
            return None
        return payload

    def _proxy_responses(self, payload: dict[str, Any]) -> None:
        attempts: list[dict[str, Any]] = []
        for attempt_index, upstream in enumerate(self.gateway_config.upstreams, start=1):
            request = build_upstream_request(upstream, payload, self.headers)
            try:
                with urllib.request.urlopen(request, timeout=upstream.timeout_seconds) as response:  # noqa: S310 - configured operator URL
                    self._relay_success(response, upstream_id=upstream.id, stream=bool(payload.get("stream")))
                    return
            except urllib.error.HTTPError as exc:
                body = exc.read()
                attempts.append({"upstream": upstream.id, "status": exc.code})
                if _is_retryable_status(exc.code, self.gateway_config, attempt_index):
                    continue
                self._relay_error(exc, body, upstream_id=upstream.id)
                return
            except (urllib.error.URLError, TimeoutError, socket.timeout) as exc:
                attempts.append({"upstream": upstream.id, "error": type(exc).__name__})
                if attempt_index <= self.gateway_config.max_failovers:
                    continue
                break
        self._send_json(502, {"error": "all_upstreams_failed", "attempts": attempts})

    def _relay_success(self, response: Any, *, upstream_id: str, stream: bool) -> None:
        self.send_response(response.status)
        if stream:
            for key, value in _response_headers_from_upstream(response, body_length=None, upstream_id=upstream_id):
                self.send_header(key, value)
            self.end_headers()
            self.close_connection = True
            while True:
                chunk = response.read(8192)
                if not chunk:
                    break
                self.wfile.write(chunk)
                self.wfile.flush()
            return
        body = response.read()
        for key, value in _response_headers_from_upstream(response, body_length=len(body), upstream_id=upstream_id):
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def _relay_error(self, exc: urllib.error.HTTPError, body: bytes, *, upstream_id: str) -> None:
        self.send_response(exc.code)
        for key, value in _response_headers_from_upstream(exc, body_length=len(body), upstream_id=upstream_id):
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)

    def _send_json(self, status: int, payload: dict[str, Any], headers: dict[str, str] | None = None) -> None:
        body = _json_bytes(payload)
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(body)))
        for key, value in (headers or {}).items():
            self.send_header(key, value)
        self.end_headers()
        self.wfile.write(body)


class GatewayServer(ThreadingHTTPServer):
    def __init__(self, server_address: tuple[str, int], gateway_config: GatewayConfig, *, quiet: bool = False):
        super().__init__(server_address, GatewayHandler)
        self.gateway_config = gateway_config
        self.quiet = quiet


def serve(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    server = GatewayServer((args.host, args.port), config, quiet=args.quiet)
    print(f"codex responses gateway listening on http://{args.host}:{args.port}", flush=True)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        pass
    finally:
        server.server_close()
    return 0


def check_config(args: argparse.Namespace) -> int:
    config = load_config(args.config)
    payload = {
        "ok": True,
        "upstreams": [item.id for item in config.upstreams],
        "auth_required": bool(config.auth_token),
        "retry_statuses": sorted(config.retry_statuses),
        "max_failovers": config.max_failovers,
    }
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    return 0


def example_config(_: argparse.Namespace) -> int:
    print(json.dumps({
        "auth": {"bearer_token_env": "CODEX_GATEWAY_API_KEY"},
        "routing": {"strategy": "ordered_failover", "max_failovers": 1, "retry_statuses": sorted(DEFAULT_RETRY_STATUSES)},
        "upstreams": [
            {
                "id": "openai-primary",
                "base_url": "https://api.openai.com/v1",
                "api_key_env": "OPENAI_API_KEY",
                "model_map": {"gpt-5.4": "gpt-5.4"},
                "timeout_seconds": 600,
            }
        ],
    }, ensure_ascii=False, indent=2))
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    serve_parser = sub.add_parser("serve", help="Run the gateway HTTP server")
    serve_parser.add_argument("--config", required=True)
    serve_parser.add_argument("--host", default="127.0.0.1")
    serve_parser.add_argument("--port", type=int, default=8787)
    serve_parser.add_argument("--quiet", action="store_true")
    serve_parser.set_defaults(func=serve)

    check_parser = sub.add_parser("check-config", help="Validate and summarize a gateway config")
    check_parser.add_argument("--config", required=True)
    check_parser.set_defaults(func=check_config)

    example_parser = sub.add_parser("example-config", help="Print an example gateway config")
    example_parser.set_defaults(func=example_config)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_parser()
    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
