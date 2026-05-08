# Agent 团队看板独立部署方案

## 需求摘要

将 `my-agent-teams/dashboard/` 部署到 `chiraliumai.cn` 生产域名下，独立于开罗尔平台运行，加简单认证保护。

## 现有基础设施（参照物）

| 组件 | 配置 | 端口 |
|------|------|------|
| Cloudflare Tunnel | `~/.cloudflared/config.yml` → `chiraliumai.cn` / `www.chiraliumai.cn` | 外部流量入口 |
| Caddy（开罗尔） | `Caddyfile.tunnel`，监听 `127.0.0.1:8088`，反代到后端 `:8000` + 前端静态文件 | 8088 |
| 开罗尔后端 | Uvicorn，`127.0.0.1:8000` | 8000 |
| 看板（本地开发） | Flask，`dashboard/task-board.sqlite3`，`127.0.0.1:5001` | 5001 |

**关键约束**：看板是纯 Flask + SQLite，零依赖开罗尔代码、数据库、Docker。只读本地文件系统上的 task JSON。

---

## 方案选择：子域名 + Cloudflare Tunnel 直连

### 推荐方案：`board.chiraliumai.cn` 独立子域名

**为什么不用路径隔离（`chiraliumai.cn/board/`）**：
- 路径隔离需要在 Caddy 里加规则，Caddy 是开罗尔的入口，改它就违反"不影响开罗尔"的约束
- 开罗尔的 Caddyfile 当前不在 tunnel 模式下使用（tunnel 直连 8088），加路径会让路由逻辑耦合

**为什么不用 Docker**：
- 看板是单进程 Flask + 单文件 SQLite，Docker 是过度工程
- 开罗尔已有 Docker 组件（PostgreSQL、FunASR），加容器增加运维复杂度
- 本机 systemd/launchd 足够可靠

### 架构图

```
用户浏览器
    │
    ▼
Cloudflare CDN（board.chiraliumai.cn DNS → Tunnel）
    │
    ▼
cloudflared tunnel（本机，新增 ingress 规则）
    │  board.chiraliumai.cn → http://127.0.0.1:5002
    ▼
看板 Flask（gunicorn，127.0.0.1:5002）
    │  ↕ 认证（HTTP Basic Auth，Flask 中间件）
    ▼
SQLite（/opt/task-board/task-board.sqlite3）
    │  数据来源：rsync 定时同步
    ▼
开发机 ~/Desktop/work/my-agent-teams/.omx/task-board/task-board.sqlite3
```

---

## 部署架构详细设计

### 1. Cloudflare Tunnel 配置变更

在 `~/.cloudflared/config.yml` 新增一条 ingress 规则：

```yaml
tunnel: 575873d2-b13d-40cf-8ed6-a1da627d0a51
credentials-file: /Users/lin/.cloudflared/575873d2-b13d-40cf-8ed6-a1da627d0a51.json
ingress:
  - hostname: chiraliumai.cn
    service: http://127.0.0.1:8088
  - hostname: www.chiraliumai.cn
    service: http://127.0.0.1:8088
  - hostname: board.chiraliumai.cn       # ← 新增
    service: http://127.0.0.1:5002       # ← 看板独立端口
  - service: http_status:404
```

**操作步骤**：
1. DNS：在 Cloudflare Dashboard 为 `board.chiraliumai.cn` 添加 CNAME 记录指向 `575873d2-b13d-40cf-8ed6-a1da627d0a51.cfargotunnel.com`（与主域名相同 tunnel）
2. 修改 config.yml，新增 ingress 规则
3. 重启 cloudflared：`brew services restart cloudflared` 或 kill + 重启

**影响范围**：只改 cloudflared 配置，开罗尔的 Caddy / 后端 / Docker 完全不受影响。Tunnel 规则匹配是 hostname 精确匹配，互不干扰。

### 2. 看板应用部署

#### 2.1 目录结构

```
/opt/task-board/
├── venv/                          # Python 虚拟环境
├── app/                           # 看板代码（从 dashboard/ 复制）
│   ├── __init__.py
│   ├── app.py
│   ├── db.py
│   ├── ingest.py
│   ├── metrics.py
│   ├── query.py
│   ├── templates/
│   ├── static/
│   └── requirements.txt
├── task-board.sqlite3             # 生产数据库（从开发机同步）
├── .htpasswd                      # 认证凭据
└── gunicorn.conf.py               # gunicorn 配置
```

#### 2.2 Python 环境

```bash
python3 -m venv /opt/task-board/venv
/opt/task-board/venv/bin/pip install flask gunicorn
```

#### 2.3 认证方案：HTTP Basic Auth（Flask 中间件）

在 `app.py` 的 `create_app()` 中添加 before_request 钩子：

```python
import functools
import os
import bcrypt

def _check_basic_auth(request):
    auth = request.authorization
    if not auth:
        return False
    # 从环境变量读取凭据，避免硬编码
    valid_user = os.getenv('TASK_BOARD_AUTH_USER', 'admin')
    valid_hash = os.getenv('TASK_BOARD_AUTH_PASS_HASH', '')
    if not valid_hash:
        return False
    return (
        auth.username == valid_user
        and bcrypt.checkpw(auth.password.encode(), valid_hash.encode())
    )
```

**为什么选 Basic Auth 而不是 token**：
- 看板是内部工具，使用者只有林总工和少数人
- Basic Auth 浏览器原生支持，无需额外前端逻辑
- bcrypt 哈希存储，满足基本安全要求
- 如需更灵活的访问控制，后续可升级为 Cloudflare Access（零改动应用代码）

**凭据管理**：
```bash
# 生成密码哈希
python3 -c "import bcrypt; print(bcrypt.hashpw(b'YOUR_PASSWORD', bcrypt.gensalt()).decode())"

# 写入环境变量文件
cat > /opt/task-board/.env << 'EOF'
TASK_BOARD_AUTH_USER=admin
TASK_BOARD_AUTH_PASS_HASH=$2b$12$xxxxx
TASK_BOARD_DB_PATH=/opt/task-board/task-board.sqlite3
TASK_BOARD_HOST=127.0.0.1
TASK_BOARD_PORT=5002
EOF
```

#### 2.4 gunicorn 配置

`/opt/task-board/gunicorn.conf.py`：

```python
bind = "127.0.0.1:5002"
workers = 2
threads = 4
timeout = 30
preload_app = True
```

启动命令：
```bash
cd /opt/task-board
source venv/bin/activate
gunicorn --config gunicorn.conf.py "app.app:create_app()"
```

### 3. 进程管理：macOS launchd

macOS 不使用 systemd，使用 launchd 管理常驻进程。

`~/Library/LaunchAgents/com.chiralium.task-board.plist`：

```xml
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.chiralium.task-board</string>
    <key>ProgramArguments</key>
    <array>
        <string>/opt/task-board/venv/bin/gunicorn</string>
        <string>--config</string>
        <string>/opt/task-board/gunicorn.conf.py</string>
        <string>app.app:create_app()</string>
    </array>
    <key>WorkingDirectory</key>
    <string>/opt/task-board</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>TASK_BOARD_AUTH_USER</key>
        <string>admin</string>
        <key>TASK_BOARD_AUTH_PASS_HASH</key>
        <string>PLACEHOLDER_PUT_REAL_HASH_HERE</string>
        <key>TASK_BOARD_DB_PATH</key>
        <string>/opt/task-board/task-board.sqlite3</string>
    </dict>
    <key>RunAtLoad</key>
    <true/>
    <key>KeepAlive</key>
    <true/>
    <key>StandardOutPath</key>
    <string>/opt/task-board/logs/stdout.log</string>
    <key>StandardErrorPath</key>
    <string>/opt/task-board/logs/stderr.log</string>
</dict>
</plist>
```

操作：
```bash
mkdir -p /opt/task-board/logs
launchctl load ~/Library/LaunchAgents/com.chiralium.task-board.plist
```

### 4. 数据同步策略

看板数据源是 SQLite 文件，需要在开发机本地的最新数据同步到生产路径。

#### 方案：rsync + cron（推荐）

看板的 SQLite 数据由 `ingest.py` 从 tasks 目录生成。本地 task-watcher 已在做定时 ingest，只需把生成的 db 文件同步到生产路径。

```bash
# 同步脚本 /opt/task-board/sync-db.sh
#!/bin/bash
set -euo pipefail

SRC="/Users/lin/Desktop/work/my-agent-teams/.omx/task-board/task-board.sqlite3"
DST="/opt/task-board/task-board.sqlite3"

if [ ! -f "$SRC" ]; then
    echo "源数据库不存在: $SRC"
    exit 1
fi

# SQLite 安全同步：先用 .backup 命令生成一致性副本，再 rsync
# 避免复制 WAL 中间态
TMP="/opt/task-board/task-board.sqlite3.tmp"
sqlite3 "$SRC" ".backup '$TMP'"

# 原子替换
mv "$TMP" "$DST"

echo "[$(date)] 同步完成: $(stat -f%z "$DST") bytes"
```

**频率**：cron 每 5 分钟执行一次
```bash
*/5 * * * * /opt/task-board/sync-db.sh >> /opt/task-board/logs/sync.log 2>&1
```

**为什么用 `sqlite3 .backup` 而不是直接 rsync**：
- 直接 rsync 一个 WAL 模式的 SQLite 可能复制到不一致的中间状态
- `.backup` 生成一个完整的、自包含的 snapshot，不含 WAL/SHM 副文件
- gunicorn 的 preload_app 模式下，每个请求会重新打开连接，不会读到过期数据

#### 替代方案：远程 ingest（暂不推荐）

在生产路径直接运行 `ingest.py`，让它读 NFS/共享目录下的 tasks。但这要求 tasks 目录也同步到生产路径，复杂度更高，且当前生产机就是同一台 Mac，没必要。

### 5. 域名 / DNS 配置

在 Cloudflare Dashboard 操作：

1. **DNS** → 选择 `chiraliumai.cn` 域
2. **添加记录**：
   - Type: `CNAME`
   - Name: `board`
   - Target: `575873d2-b13d-40cf-8ed6-a1da627d0a51.cfargotunnel.com`
   - Proxy status: Proxied（橙色云朵）
3. 保存，等 TTL 生效（通常 < 30s）

**SSL**：Cloudflare Tunnel 自动处理 HTTPS，无需额外证书配置。浏览器到 Cloudflare 是 HTTPS，Cloudflare 到本机 tunnel 是加密的，tunnel 到 gunicorn 是 localhost HTTP——安全无问题。

### 6. 完整部署清单

按顺序执行，预计 30 分钟内完成：

| # | 步骤 | 耗时 | 风险 |
|---|------|------|------|
| 1 | Cloudflare DNS 添加 `board.chiraliumai.cn` CNAME | 2min | 无 |
| 2 | 修改 `~/.cloudflared/config.yml`，新增 ingress 规则 | 1min | 需重启 tunnel |
| 3 | 重启 cloudflared tunnel | 1min | 开罗尔服务中断 ~5s |
| 4 | 创建 `/opt/task-board/` 目录结构 | 2min | 无 |
| 5 | 复制看板代码到 `/opt/task-board/app/` | 2min | 无 |
| 6 | 创建 venv + 安装依赖（flask, gunicorn, bcrypt） | 3min | 无 |
| 7 | 生成认证密码哈希，写入 .env | 2min | 无 |
| 8 | 首次数据同步（sqlite3 .backup → /opt/task-board/） | 1min | 无 |
| 9 | 创建 launchd plist，load 并启动 gunicorn | 2min | 无 |
| 10 | 配置 cron 定时同步 | 1min | 无 |
| 11 | 浏览器访问 `https://board.chiraliumai.cn` 验证 | 2min | 无 |

### 7. 回滚方案

如果出问题，按以下步骤回滚，不影响开罗尔：

1. 卸载 launchd：`launchctl unload ~/Library/LaunchAgents/com.chiralium.task-board.plist`
2. 从 cloudflared config.yml 删除 `board.chiraliumai.cn` ingress 规则
3. 重启 cloudflared
4. 删除 DNS 记录（可选，留着也无害）

**开罗尔零影响验证**：回滚过程中，`chiraliumai.cn` / `www.chiraliumai.cn` 的 ingress 规则完全不变，Caddy 不变，后端不变。

---

## 安全评估

| 维度 | 措施 |
|------|------|
| 传输加密 | Cloudflare Tunnel 全链路加密，无需自管证书 |
| 身份认证 | HTTP Basic Auth + bcrypt 哈希 |
| 访问控制 | Cloudflare Proxy 模式隐藏源站 IP |
| 数据安全 | SQLite 只读查询，无写操作暴露 |
| 隔离性 | 独立端口（5002），独立进程（gunicorn），独立数据副本 |
| 日志 | launchd 记录 stdout/stderr 到文件，可排查 |

## 后续优化（非本次必须）

- **Cloudflare Access**：替代 Basic Auth，支持 SSO / 邮箱白名单，无需应用改代码
- **自动代码更新**：git pull + gunicorn reload 的简单脚本
- **监控告警**：看板 `/api/health` 接口 + cron 检查，异常时飞书通知
- **HTTPS 环境变量保护**：将 .env 中的密码哈希移到 macOS Keychain 或加密文件
