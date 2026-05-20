#!/bin/bash
# Feishu message push script for my-agent-teams notifications.
# Usage: echo "message" | ./feishu-push.sh
#   or: ./feishu-push.sh "single line message"
#
# Default secret source: ./config.local.json (ignored by git).
# Override path with FEISHU_CONFIG_PATH if needed.

set -u

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
WORKSPACE_ROOT="$(cd "$SCRIPT_DIR/.." && pwd)"
CONFIG_FILE="${FEISHU_CONFIG_PATH:-$WORKSPACE_ROOT/config.local.json}"

load_feishu_config() {
  python3 - "$CONFIG_FILE" <<'PYCONFIG'
import json
import sys
from pathlib import Path

path = Path(sys.argv[1]).expanduser()
if not path.exists():
    raise SystemExit(0)
try:
    payload = json.loads(path.read_text(encoding='utf-8'))
except Exception as exc:
    print(f"ERROR: failed to read config {path}: {exc}", file=sys.stderr)
    raise SystemExit(2)
notifications = payload.get('notifications') or {}
print(str(notifications.get('feishu_receive_id') or notifications.get('feishu_open_id') or ''))
print(str(notifications.get('feishu_app_id') or ''))
print(str(notifications.get('feishu_app_secret') or ''))
PYCONFIG
}

CONFIG_VALUES="$(load_feishu_config)"
CONFIG_RC=$?
if [ "$CONFIG_RC" -ne 0 ]; then
  exit "$CONFIG_RC"
fi
CONFIG_RECEIVE_ID="$(printf '%s\n' "$CONFIG_VALUES" | sed -n '1p')"
CONFIG_APP_ID="$(printf '%s\n' "$CONFIG_VALUES" | sed -n '2p')"
CONFIG_APP_SECRET="$(printf '%s\n' "$CONFIG_VALUES" | sed -n '3p')"

RECEIVE_ID="${FEISHU_RECEIVE_ID:-${CONFIG_RECEIVE_ID:-}}"
APP_ID="${FEISHU_APP_ID:-$CONFIG_APP_ID}"
APP_SECRET="${FEISHU_APP_SECRET:-$CONFIG_APP_SECRET}"

if [ -z "$APP_ID" ] || [ -z "$APP_SECRET" ]; then
  echo "ERROR: missing Feishu app credentials. Set them in $CONFIG_FILE or override with FEISHU_APP_ID/FEISHU_APP_SECRET." >&2
  exit 1
fi

IMAGE_FILE=""
while [ $# -gt 0 ]; do
  case "$1" in
    -i)
      if [ $# -lt 2 ]; then
        echo "ERROR: -i requires an image file path" >&2
        exit 1
      fi
      IMAGE_FILE="$2"
      shift 2
      ;;
    *) break ;;
  esac
done

MESSAGE=""
if [ $# -gt 0 ]; then
  MESSAGE="$*"
elif [ -z "$IMAGE_FILE" ]; then
  MESSAGE=$(cat)
fi

TOKEN_PAYLOAD=$(FEISHU_APP_ID_VALUE="$APP_ID" FEISHU_APP_SECRET_VALUE="$APP_SECRET" python3 - <<'PYTOKEN'
import json
import os
print(json.dumps({
    'app_id': os.environ['FEISHU_APP_ID_VALUE'],
    'app_secret': os.environ['FEISHU_APP_SECRET_VALUE'],
}))
PYTOKEN
)

TOKEN_RESPONSE=$(curl --fail --silent --show-error \
  --connect-timeout "${FEISHU_CONNECT_TIMEOUT:-5}" \
  --max-time "${FEISHU_TOKEN_TIMEOUT:-15}" \
  "https://open.feishu.cn/open-apis/auth/v3/tenant_access_token/internal" \
  -H "Content-Type: application/json" \
  -d "$TOKEN_PAYLOAD") || {
  echo "ERROR: Failed to request tenant access token" >&2
  exit 1
}

TENANT_TOKEN=$(printf '%s' "$TOKEN_RESPONSE" | python3 -c "import sys,json; print(json.load(sys.stdin).get('tenant_access_token',''))" 2>/dev/null || true)
if [ -z "$TENANT_TOKEN" ]; then
  echo "ERROR: Failed to parse tenant access token" >&2
  exit 1
fi

FEISHU_MESSAGE="$MESSAGE" \
FEISHU_RECEIVE_ID_EFFECTIVE="$RECEIVE_ID" \
FEISHU_TENANT_TOKEN="$TENANT_TOKEN" \
FEISHU_IMAGE_FILE="$IMAGE_FILE" \
python3 - <<'PYFEISHU'
import json
import os
import sys
import urllib.error
import urllib.request

msg = os.environ.get('FEISHU_MESSAGE', '').strip()
receive_id = os.environ['FEISHU_RECEIVE_ID_EFFECTIVE']
token = os.environ['FEISHU_TENANT_TOKEN']
image_file = os.environ.get('FEISHU_IMAGE_FILE', '')
message_uuid = os.environ.get('FEISHU_MESSAGE_UUID', '').strip()

if not msg and not image_file:
    print('ERROR: empty message and no image', file=sys.stderr)
    sys.exit(1)

image_key = ''
if image_file:
    boundary = '----FeishuBoundary7MA4YWxkTrZu0gW'
    with open(image_file, 'rb') as f:
        image_data = f.read()
    body = b''.join([
        f'--{boundary}\r\n'.encode('utf-8'),
        b'Content-Disposition: form-data; name="image_type"\r\n\r\n',
        b'message\r\n',
        f'--{boundary}\r\n'.encode('utf-8'),
        f'Content-Disposition: form-data; name="image"; filename="{os.path.basename(image_file)}"\r\n'.encode('utf-8'),
        b'Content-Type: application/octet-stream\r\n\r\n',
        image_data,
        f'\r\n--{boundary}--\r\n'.encode('utf-8'),
    ])

    req = urllib.request.Request(
        'https://open.feishu.cn/open-apis/im/v1/images',
        data=body,
        headers={
            'Authorization': f'Bearer {token}',
            'Content-Type': f'multipart/form-data; boundary={boundary}',
        },
    )
    try:
        resp = urllib.request.urlopen(req, timeout=int(os.environ.get('FEISHU_IMAGE_TIMEOUT', '30')))
        data = json.loads(resp.read().decode('utf-8'))
        if data.get('code') == 0:
            image_key = data['data']['image_key']
        else:
            print(f'ERROR: upload image failed: {json.dumps(data, ensure_ascii=False)}', file=sys.stderr)
            sys.exit(1)
    except Exception as exc:
        print(f'ERROR: upload image: {exc}', file=sys.stderr)
        sys.exit(1)

if image_key:
    payload = {
        'receive_id': receive_id,
        'msg_type': 'image',
        'content': json.dumps({'image_key': image_key}),
    }
else:
    payload = {
        'receive_id': receive_id,
        'msg_type': 'text',
        'content': json.dumps({'text': msg}),
    }

if message_uuid:
    payload['uuid'] = message_uuid

def send_payload(request_payload: dict) -> dict:
    req = urllib.request.Request(
        'https://open.feishu.cn/open-apis/im/v1/messages?receive_id_type=open_id',
        data=json.dumps(request_payload).encode('utf-8'),
        headers={
            'Authorization': f'Bearer {token}',
            'Content-Type': 'application/json',
        },
    )
    resp = urllib.request.urlopen(req, timeout=int(os.environ.get('FEISHU_SEND_TIMEOUT', '10')))
    return json.loads(resp.read().decode('utf-8'))


def finish_success(note: str = '') -> None:
    suffix = f' ({note})' if note else ''
    print(f'Message sent successfully{suffix}')
    if image_file and os.path.exists(image_file):
        os.remove(image_file)
    raise SystemExit(0)


try:
    data = send_payload(payload)
    if data.get('code') == 0:
        finish_success()
    print(f'ERROR: {json.dumps(data, ensure_ascii=False)}', file=sys.stderr)
    sys.exit(1)
except urllib.error.HTTPError as exc:
    response_body = ''
    try:
        response_body = exc.read().decode('utf-8', errors='replace')
    except Exception:
        response_body = ''

    if payload.get('uuid') and exc.code == 400:
        retry_payload = dict(payload)
        retry_payload.pop('uuid', None)
        try:
            retry_data = send_payload(retry_payload)
            if retry_data.get('code') == 0:
                print('WARN: Feishu rejected message uuid; retried without uuid', file=sys.stderr)
                finish_success('retried without uuid')
            print(f'ERROR: {json.dumps(retry_data, ensure_ascii=False)}', file=sys.stderr)
            sys.exit(1)
        except Exception as retry_exc:
            print(f'ERROR: retry without uuid failed after HTTP 400: {retry_exc}', file=sys.stderr)
            sys.exit(1)

    detail = response_body or getattr(exc, 'reason', '') or str(exc)
    print(f'ERROR: HTTP Error {exc.code}: {detail}', file=sys.stderr)
    sys.exit(1)
except Exception as exc:
    print(f'ERROR: {exc}', file=sys.stderr)
    sys.exit(1)
PYFEISHU
