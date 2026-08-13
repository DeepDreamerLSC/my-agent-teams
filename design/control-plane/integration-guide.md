# 外部项目接入指南

## 注册项目

```bash
python3 scripts/control-plane.py project register \
  --id billing-service \
  --name billing-service \
  --repo-root /path/to/billing-service \
  --branch main \
  --control-plane-url http://127.0.0.1:5001
python3 scripts/control-plane.py project check billing-service
python3 scripts/control-plane.py project scope-check billing-service --path /path/to/billing-service/src
```

## 预览并应用最小接入层

```bash
python3 scripts/control-plane.py project bootstrap \
  --project-id billing-service \
  --repo-root /path/to/billing-service \
  --control-plane-url http://127.0.0.1:5001

python3 scripts/control-plane.py project bootstrap \
  --project-id billing-service \
  --repo-root /path/to/billing-service \
  --control-plane-url http://127.0.0.1:5001 \
  --apply
python3 scripts/control-plane.py project bootstrap-check --repo-root /path/to/billing-service
```

工具只生成 `.my-agent-teams/control-plane.json`、AGENTS 引用块、共享 Skill 引用和白名单 Hook。已有 `AGENTS.md` 内容保留；已有 managed manifest、部分 marker 或其他项目标识都会报冲突并停止。Hook 只提交项目/会话/阶段/心跳/错误和摘要/交付物引用，配置 `MY_AGENT_TEAMS_CONTROL_PLANE_TOKEN` 时 API 事件接口要求 Bearer token。

## 绑定已有或新建会话

```bash
python3 scripts/control-plane.py session register \
  --project-id billing-service --requirement-id req_x \
  --role developer --backend codex --thread-id thread_x \
  --cwd /path/to/billing-service
python3 scripts/control-plane.py session bind session_x --task-id task_x
python3 scripts/control-plane.py session heartbeat session_x --idempotency-key hb_x --sequence 1 --status busy
```

新建会话走统一 backend 接口：

```bash
python3 scripts/control-plane.py session create \
  --project-id billing-service --requirement-id req_x \
  --role developer --backend codex --cwd /path/to/billing-service
```

本机 Codex CLI 当前公开提供实验性 App Server 协议，可用下面的命令生成对应版本 schema，供 bridge/SDK 适配：

```bash
codex app-server generate-json-schema --experimental --out /tmp/codex-app-server-schema
```

控制面通过 `MY_AGENT_TEAMS_CODEX_APP_SERVER_BRIDGE` 接入一个可替换的官方 App Server/SDK bridge。bridge 接收一行 JSON action 请求并返回一行 JSON 结果，由 bridge 内部映射 `ThreadStart`、`ThreadList`、`ThreadRead` 和健康/断开操作；控制面不读取 Codex Desktop 私有数据库或 transcript 文件。没有配置 bridge 时，`session create --backend codex` 和 probe 会返回 `unsupported`，不会伪造在线状态。

## 卸载

```bash
python3 scripts/control-plane.py project uninstall --repo-root /path/to/billing-service
python3 scripts/control-plane.py project uninstall --repo-root /path/to/billing-service --apply
```

先看 preview，再应用；卸载会把 managed 文件移动到时间戳备份目录，只移除明确生成的 AGENTS marker。
