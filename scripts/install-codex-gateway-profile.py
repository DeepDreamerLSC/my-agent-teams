#!/usr/bin/env python3
"""Install a managed Codex profile block for the local Responses Gateway."""
from __future__ import annotations

import argparse
import os
import shutil
import tempfile
from dataclasses import dataclass
from pathlib import Path

BEGIN = "# BEGIN my-agent-teams codex-responses-gateway"
END = "# END my-agent-teams codex-responses-gateway"
DEFAULT_PROFILES = "pm-team:gpt-5.4:high,arch-team:gpt-5.4:high,dev-team:gpt-5.4:medium,review-team:gpt-5.4:high"


@dataclass(frozen=True)
class Profile:
    name: str
    model: str
    effort: str


def parse_profiles(raw: str) -> list[Profile]:
    profiles: list[Profile] = []
    for item in raw.split(','):
        item = item.strip()
        if not item:
            continue
        parts = item.split(':')
        if len(parts) != 3 or not all(parts):
            raise ValueError(f"invalid profile spec: {item!r}; expected name:model:effort")
        profiles.append(Profile(name=parts[0], model=parts[1], effort=parts[2]))
    if not profiles:
        raise ValueError('at least one profile is required')
    return profiles


def render_block(*, provider: str, provider_name: str, gateway_base_url: str, api_key_env: str, profiles: list[Profile]) -> str:
    lines = [
        BEGIN,
        f"[model_providers.{provider}]",
        f'name = "{provider_name}"',
        f'base_url = "{gateway_base_url.rstrip("/")}"',
        'wire_api = "responses"',
        f'env_key = "{api_key_env}"',
        'requires_openai_auth = false',
        '',
    ]
    for profile in profiles:
        lines.extend([
            f"[profiles.{profile.name}]",
            f'model_provider = "{provider}"',
            f'model = "{profile.model}"',
            f'model_reasoning_effort = "{profile.effort}"',
            '',
        ])
    lines.append(END)
    lines.append('')
    return '\n'.join(lines)


def replace_block(existing: str, block: str) -> str:
    start = existing.find(BEGIN)
    end = existing.find(END)
    if start == -1 and end == -1:
        separator = '' if not existing or existing.endswith('\n') else '\n'
        return f"{existing}{separator}{block}"
    if start == -1 or end == -1 or end < start:
        raise ValueError('existing Codex config has an incomplete managed gateway block')
    end += len(END)
    while end < len(existing) and existing[end] in '\r\n':
        end += 1
    separator = '' if start == 0 or existing[start - 1] == '\n' else '\n'
    return existing[:start] + separator + block + existing[end:]


def atomic_write(path: Path, content: str) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    with tempfile.NamedTemporaryFile('w', delete=False, dir=str(path.parent), encoding='utf-8') as tmp:
        tmp.write(content)
        tmp_path = Path(tmp.name)
    os.replace(tmp_path, path)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--codex-config', default=str(Path.home() / '.codex' / 'config.toml'))
    parser.add_argument('--provider', default='codex-gateway')
    parser.add_argument('--provider-name', default='Codex Responses Gateway')
    parser.add_argument('--gateway-base-url', default='http://127.0.0.1:8787/v1')
    parser.add_argument('--api-key-env', default='CODEX_GATEWAY_API_KEY')
    parser.add_argument('--profiles', default=DEFAULT_PROFILES, help='comma-separated name:model:effort entries')
    parser.add_argument('--dry-run', action='store_true')
    args = parser.parse_args()

    profiles = parse_profiles(args.profiles)
    block = render_block(
        provider=args.provider,
        provider_name=args.provider_name,
        gateway_base_url=args.gateway_base_url,
        api_key_env=args.api_key_env,
        profiles=profiles,
    )
    path = Path(args.codex_config).expanduser()
    existing = path.read_text(encoding='utf-8') if path.exists() else ''
    rendered = replace_block(existing, block)
    if args.dry_run:
        print(rendered, end='')
        return 0
    if path.exists():
        backup = path.with_suffix(path.suffix + '.bak')
        shutil.copy2(path, backup)
        print(f'backed up {path} -> {backup}')
    atomic_write(path, rendered)
    print(f'installed Codex gateway profiles into {path}')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
