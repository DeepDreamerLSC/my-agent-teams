# my-agent-teams

> 基于 OpenClaw + tmux 的多智能体协作框架
> 通过文件系统做状态管理，tmux 做消息通道，watcher 做状态监控，实现 AI agent 之间的任务派发、执行、审查和集成。

## 这是什么

一个让多个 AI agent（Claude Code / Codex）协同完成开发任务的框架。

不依赖 WebSocket、HTTP API 或消息队列——只用 **tmux session + 文件系统 + shell 脚本** 就能让 agent 之间可靠协作。

### 核心理念

```
Agent 之间不直接对话。
所有通信通过文件中介和 tmux send-keys。
状态变更通过 watcher 脚本自动检测和通知。
```

### 当前团队配置

```
PM（pm-chief）— 需求分析、任务拆解、进度跟踪
├── 架构师（arch-1）— 方案设计、接口契约、技术选型
├── 前端开发（fe-1）— 页面、组件、样式
├── 后端开发（be-1）— API、数据库、业务逻辑
├── 测试（qa-1）— 功能验证、回归测试
└── 审查（review-1）— 代码审查、文档审阅
```

### 工作目录隔离（当前方案）

- 每个 agent 都从独立工作目录启动：`agents/<agent-id>/`
- Claude Code 读取当前工作目录下的 `CLAUDE.md`
- Codex agent 目录读取当前工作目录下的 `AGENT.md`
- 根目录 `CLAUDE.md` / `AGENTS.md` 只保留**通用规则**
- `instruction.md` 回归纯任务描述：只写做什么、改哪些文件、验收标准，不再注入角色身份
- `tasks/`、`scripts/`、`config.json`、`prompts/` 等共享资源统一通过**绝对路径**访问
- 新任务 ID 必须使用中文标题式名称，例如：`修复Word生成质量问题`、`Agent目录隔离方案`
- `T-001` 这类旧编号和纯英文 slug 不允许用于新建任务

## 快速开始

### 前置条件

- macOS / Linux
- tmux
- jq
- Python 3
- 至少 2 个 tmux session 运行 Claude Code 或 Codex（一个当 PM，一个当执行 agent）

### 1. 启动 agent（进入独立工作目录）

```bash
# PM（Claude Code）
cd /Users/lin/Desktop/work/my-agent-teams/agents/pm-chief

# 架构师（Codex）
cd /Users/lin/Desktop/work/my-agent-teams/agents/arch-1

# 前端
cd /Users/lin/Desktop/work/my-agent-teams/agents/fe-1

# 后端
cd /Users/lin/Desktop/work/my-agent-teams/agents/be-1

# QA
cd /Users/lin/Desktop/work/my-agent-teams/agents/qa-1

# Reviewer
cd /Users/lin/Desktop/work/my-agent-teams/agents/review-1
```

各 agent 启动后先读取各自目录下的角色文件再按其中规则工作：
- Claude Code：`CLAUDE.md`（`pm-chief`、`fe-1`、`qa-1`）
- Codex：`AGENT.md`（`arch-1`、`be-1`、`review-1`）

### 2. 启动 watcher

```bash
# 前台运行（调试用）
SCAN_INTERVAL=3 /Users/lin/Desktop/work/my-agent-teams/scripts/task-watcher.sh

# 后台运行（生产用）
SCAN_INTERVAL=3 /Users/lin/Desktop/work/my-agent-teams/scripts/task-watcher.sh >> /tmp/agent-teams-watcher.log 2>&1 &
```

### 3. 创建任务

```bash
/Users/lin/Desktop/work/my-agent-teams/scripts/create-task.sh 实现用户登录页 "实现用户登录页" fe-1 frontend chiralium "frontend/src/pages/Login.tsx" false false reviewer dev dev
```

这会创建 `tasks/实现用户登录页/` 目录，包含：
- `task.json` — 任务定义（状态=pending）
- `instruction.md` — 纯任务指令模板（需 PM 填充任务目标、write_scope、验收标准等）
- `transitions.jsonl` — 状态变更日志

### 4. 派发任务

```bash
/Users/lin/Desktop/work/my-agent-teams/scripts/dispatch-task.sh /Users/lin/Desktop/work/my-agent-teams/tasks/实现用户登录页/task.json
```

- 将 `task.json.status` 改为 `dispatched`
- 通过 `tmux send-keys` 将 instruction.md 内容发送给目标 agent 的 tmux session

### 5. Agent 确认

Agent 收到任务后写 `ack.json`：

```json
{
  "agent": "fe-1",
  "task_id": "实现用户登录页",
  "status": "acknowledged",
  "timestamp": "2026-04-23T10:00:00+08:00"
}
```

watcher 检测到 ack.json 后自动将状态改为 `working`，并推送飞书通知。

### 6. Agent 完成任务

Agent 写 `result.json`：

```json
{
  "agent": "fe-1",
  "task_id": "实现用户登录页",
  "status": "done",
  "summary": "登录页已实现，包含手机号和微信扫码两种方式",
  "display_type": "text",
  "result": "实现详情...",
  "duration_ms": 120000
}
```

### 7. 验证

watcher 自动调用 `verify.sh`，检查：
- ack.json 格式是否正确
- result.json 格式是否正确
- write_scope 内的文件是否有变更
- 结果写入 `verify.json`

## 任务看板使用说明

项目内置了一个轻量任务看板，基于：
- SQLite（任务状态库）
- Flask（本地服务）
- ECharts（页面图表）

支持三个视图：
1. 看板视图：按 `pending / working / ready_for_merge / blocked / done` 分列
2. 甘特图：展示任务生命周期时间线
3. Agent 统计：展示工作时长、完成任务数、当前负载

### 数据库位置

默认 SQLite 文件：

```bash
/Users/lin/Desktop/work/my-agent-teams/.omx/task-board/task-board.sqlite3
```

如需覆盖，可设置环境变量：

```bash
export TASK_BOARD_DB_PATH=/your/path/task-board.sqlite3
```

### 首次使用

#### 1. 安装依赖

```bash
cd /Users/lin/Desktop/work/my-agent-teams
python3 -m pip install -r dashboard/requirements.txt
```

#### 2. 首次回填历史任务

把 `tasks/` 目录里的历史任务导入 SQLite：

```bash
cd /Users/lin/Desktop/work/my-agent-teams
python3 scripts/task-board-sync.py backfill --tasks-root ./tasks
```

#### 3. 启动看板服务

```bash
cd /Users/lin/Desktop/work/my-agent-teams
python3 -m dashboard.app
```

默认监听：
- Host: `127.0.0.1`
- Port: `5001`

访问地址：

```text
http://127.0.0.1:5001/
```

### 后续增量同步

如果 `task-watcher.sh` 正在运行，任务状态变化会自动触发增量写库，不需要手工重复 backfill。

如需手工同步某个任务目录：

```bash
cd /Users/lin/Desktop/work/my-agent-teams
python3 scripts/task-board-sync.py sync-task --task-dir ./tasks/<task-id> --source manual
```

### 常用环境变量

```bash
TASK_BOARD_HOST=0.0.0.0
TASK_BOARD_PORT=5001
TASK_BOARD_DB_PATH=/custom/path/task-board.sqlite3
```

例如局域网访问：

```bash
cd /Users/lin/Desktop/work/my-agent-teams
TASK_BOARD_HOST=0.0.0.0 TASK_BOARD_PORT=5001 python3 -m dashboard.app
```

然后访问：

```text
http://<你的机器IP>:5001/
```

### API 一览

- `GET /`：任务看板页面
- `GET /api/health`：健康检查
- `GET /api/board`：看板数据
- `GET /api/gantt`：甘特图数据
- `GET /api/agents`：Agent 统计数据

兼容别名（保留旧路径）：
- `GET /api/tasks`
- `GET /api/tasks/gantt`
- `GET /api/agents/stats`

### 故障排查

#### 页面打开但没有数据

先确认 SQLite 有数据：

```bash
cd /Users/lin/Desktop/work/my-agent-teams
python3 scripts/task-board-sync.py backfill --tasks-root ./tasks
curl http://127.0.0.1:5001/api/board
```

#### 页签点击无反应 / 页面无交互

检查前端脚本是否有语法错误：

```bash
cd /Users/lin/Desktop/work/my-agent-teams
node --check dashboard/static/js/dashboard.js
```

#### 端口占用或需要重启

```bash
lsof -nP -iTCP:5001 -sTCP:LISTEN
kill <PID>
cd /Users/lin/Desktop/work/my-agent-teams
python3 -m dashboard.app
```

## 任务生命周期

```
pending → dispatched → working → ready_for_merge → merged → archived
                                ↓
                           failed / blocked / cancelled / timeout
```

| 状态 | 触发者 | 说明 |
|------|--------|------|
| pending | PM / 开罗尔 | 任务已创建 |
| dispatched | dispatch-task.sh | 已通过 tmux 发送给 agent |
| working | watcher | 检测到 ack.json |
| ready_for_merge | watcher | 检测到 result.json + verify 通过 |
| merged | PM / integrator | 代码已合入集成分支 |
| failed | agent / watcher | 执行失败 |
| blocked | agent | 上游依赖未满足 |
| timeout | watcher | 超过 timeout_minutes 未 ack |
| cancelled | PM / 开罗尔 | 取消任务 |

## 目录结构

```
my-agent-teams/
├── config.json                      # 全局配置（团队拓扑、项目注册表、权限、通知）
├── CLAUDE.md                        # 根共享规则（Claude Code）
├── AGENTS.md                        # 根共享规则（Codex）
├── agents/                          # agent 独立工作目录
│   ├── pm-chief/
│   │   └── CLAUDE.md                # PM 角色身份与特化规则
│   ├── arch-1/
│   │   └── AGENT.md                 # 架构师角色身份与特化规则（Codex）
│   ├── fe-1/
│   │   └── CLAUDE.md
│   ├── be-1/
│   │   └── AGENT.md
│   ├── qa-1/
│   │   └── CLAUDE.md
│   └── review-1/
│       └── AGENT.md
├── tasks/                           # 所有任务
│   ├── _system/                     # watcher 运行时状态
│   │   ├── notifications.jsonl      # 通知记录
│   │   └── watcher-state/           # 各任务指纹快照
│   ├── _templates/                  # 任务模板
│   └── {task-id}/                   # 单个任务
│       ├── task.json                # 任务定义
│       ├── instruction.md           # PM 生成的纯任务指令
│       ├── ack.json                 # Agent 确认
│       ├── result.json              # Agent 结果
│       ├── verify.json              # 校验结果
│       └── transitions.jsonl        # 状态变更日志
├── scripts/                         # 运行时脚本
│   ├── create-task.sh               # 创建任务
│   ├── dispatch-task.sh             # 派发任务
│   ├── verify.sh                    # 校验任务
│   └── task-watcher.sh              # 状态监控 + 通知
├── prompts/                         # 角色 Prompt
│   ├── pm-base.md                   # PM
│   ├── architect-base.md            # 架构师
│   ├── frontend-dev-base.md         # 前端开发
│   ├── backend-dev-base.md          # 后端开发
│   ├── qa-base.md                   # 测试
│   └── reviewer-base.md             # 审查
└── design/                          # 设计文档
    ├── OpenClaw-tmux协作方案优化.md   # 主方案（v10）
    └── 分层PM演进方案.md             # 分层 PM 演进
```


### 环境隔离（Phase 1）

- `config.json.projects` 明确定义每个项目的 `dev_root` / `prod_root`
- `config.json.agents[*].workdir` 定义每个 agent 的独立启动目录
- `task.json` 需声明：`project`、`execution_mode`、`target_environment`
- `create-task.sh` 和 `dispatch-task.sh` 都会做前置校验：
  - 开发任务只能落在 `project.dev_root`
  - `prod` 路径和 `deploy` 任务在 Phase 1 仅允许 `pm-chief`

## 核心文件说明

### config.json

全局配置，定义团队拓扑和规则：

```json
{
  "version": 1,
  "phase": "phase1_minimal_closure",
  "agents_root": "/Users/lin/Desktop/work/my-agent-teams/agents",
  "shared_paths": {
    "tasks_root": "/Users/lin/Desktop/work/my-agent-teams/tasks",
    "scripts_root": "/Users/lin/Desktop/work/my-agent-teams/scripts"
  },
  "orchestration": {
    "mode": "single_pm",
    "hierarchy_ready": true,
    "root_pm": "pm-chief",
    "domains": {
      "frontend": ["fe-1"],
      "backend": ["be-1"],
      "quality": ["qa-1", "review-1"]
    }
  },
  "protected_paths": ["tasks/**", "scripts/**", "prompts/**", "config.json"],
  "notifications": {
    "feishu_open_id": "ou_xxx",
    "push_script": "/path/to/feishu-push.sh"
  }
}
```

### task.json

每个任务的核心定义：

```json
{
  "id": "实现用户登录页",
  "title": "实现用户登录页",
  "status": "pending",
  "task_level": "execution",
  "domain": "frontend",
  "owner_pm": "pm-chief",
  "assigned_agent": "fe-1",
  "review_required": true,
  "reviewer": "review-1",
  "test_required": false,
  "write_scope": ["frontend/src/pages/login/**"],
  "depends_on": [],
  "blocks": ["补充登录页测试"],
  "timeout_minutes": 30
}
```

### transitions.jsonl

追加式状态变更日志，不可变审计记录：

```jsonl
{"from":"pending","to":"dispatched","timestamp":"2026-04-23T10:00:00+08:00","reason":"pm_dispatched"}
{"from":"dispatched","to":"working","timestamp":"2026-04-23T10:00:05+08:00","reason":"ack_detected"}
{"from":"working","to":"ready_for_merge","timestamp":"2026-04-23T10:15:00+08:00","reason":"result_received"}
```

## 安全约束

- **保护路径**：agent 不能修改 `tasks/`、`scripts/`、`prompts/`、`config.json`
- **write_scope**：agent 只能修改 task.json 中声明的文件范围
- **verify 硬检查**：watcher 校验 agent 的实际 diff 是否越界
- **角色不交叉**：审查者不改代码，开发不做架构决策
- **角色来源固定**：角色身份来自 `agents/<agent-id>/CLAUDE.md` / `AGENT.md`，不再由 `instruction.md` 注入

## 设计参考

- [OpenClaw-tmux协作方案优化.md](design/OpenClaw-tmux协作方案优化.md) — 完整方案文档（v10，2200+ 行）
- [分层PM演进方案.md](design/分层PM演进方案.md) — 3-5 / 8-10 / 12-15 agent 的组织演进
- [Claude Code 源码分析](https://github.com/dadiaomengmeimei/claude-code-sourcemap-learning-notebook) — 权限模型、Query Loop、Prompt 工程等设计参考

## 演进路线

| 阶段 | Agent 数量 | 组织结构 | 状态 |
|------|-----------|---------|------|
| Phase 1 | 3-5 | 单 PM | ✅ 当前，最小闭环已落地 |
| Phase 2 | 8-10 | 总 PM + 子 PM | 🔜 hierarchy-ready schema 已就绪 |
| Phase 3 | 12-15 | Program / Domain / Pod PM | 📋 设计完成，待触发 |

## License

内部项目，不对外开源。
