# my-agent-teams - CLAUDE.md

> 项目级共享规则。角色身份不在这里区分；每个 agent 必须从自己的独立工作目录启动，并由 `agents/<agent-id>/CLAUDE.md`（Claude Code）或 `agents/<agent-id>/AGENT.md`（Codex）承载角色身份。

## 工作目录隔离

- 每个 agent 的当前工作目录必须是：`/Users/lin/Desktop/work/my-agent-teams/agents/<agent-id>`。
- Claude Code 只自动读取当前工作目录下的 `CLAUDE.md`。
- Codex agent 目录使用当前工作目录下的 `AGENT.md`。
- 当前约定：`pm-chief`、`qa-1` 使用 `CLAUDE.md`；`arch-1`、`dev-1`、`dev-2`、`review-1` 使用 `AGENT.md`。
- 不再通过 tmux session 名、环境变量或 `instruction.md` 注入来识别角色。
- `instruction.md` 现在只承担**任务描述**职责：做什么、改哪些文件、验收标准、交付物；不再承担角色注入。
- agent 目录下的角色文件负责“你是谁”；本文件只负责“所有人都要遵守什么”。
- 新任务命名**必须**使用中文标题式名称，例如：`修复Word生成质量问题`、`Agent目录隔离方案`。
- `T-001` 这类旧编号和纯英文 slug 不允许用于新建任务。

## 共享资源（必须使用绝对路径）

- 工作区根目录：`/Users/lin/Desktop/work/my-agent-teams`
- agent 工作目录根：`/Users/lin/Desktop/work/my-agent-teams/agents`
- 任务目录：`/Users/lin/Desktop/work/my-agent-teams/tasks`
- 脚本目录：`/Users/lin/Desktop/work/my-agent-teams/scripts`
- 配置文件：`/Users/lin/Desktop/work/my-agent-teams/config.json`
- 角色 prompt 目录：`/Users/lin/Desktop/work/my-agent-teams/prompts`
- 根共享规则（Claude）：`/Users/lin/Desktop/work/my-agent-teams/CLAUDE.md`
- 根共享规则（Codex）：`/Users/lin/Desktop/work/my-agent-teams/AGENTS.md`

## 向其他会话发送消息的注意事项

- **向 Codex CLI 会话发消息**：发送前**必须先按 `i` 进入插入模式**，否则文本只会显示在输入框中不会发送
  ```bash
  tmux send-keys -t <session> i
  sleep 0.5
  tmux send-keys -t <session> -l -- "消息内容"
  sleep 0.1
  tmux send-keys -t <session> Enter
  ```
- **向 Claude Code 会话发消息**（仅 qa-1）：直接 send-keys 即可，不需要 `i`

## 项目说明

这是一个多智能体协作框架。你是一个 agent，在 tmux session 中运行，与其他 agent 协同完成开发任务。

## 核心规则

- **任务管理**：所有任务通过 `tasks/` 目录下的 `task.json` 管理，不凭记忆做派发。
- **绝对路径**：访问 `tasks/`、`scripts/`、`config.json`、`prompts/` 等共享资源时，一律使用绝对路径，不依赖当前 cwd。
- **保护路径**：禁止修改 `/Users/lin/Desktop/work/my-agent-teams/tasks`、`/Users/lin/Desktop/work/my-agent-teams/scripts`、`/Users/lin/Desktop/work/my-agent-teams/prompts`、`/Users/lin/Desktop/work/my-agent-teams/config.json`、根目录 `CLAUDE.md` / `AGENTS.md`，除非上级明确下达此类任务。
- **write_scope**：只能修改 `task.json.write_scope` 中声明的文件范围。
- **A-Lite 阶段不互相私聊**：不启用 agent 私聊；但允许所有 agent 在 `chat/general/` 和 `chat/tasks/{task-id}.jsonl` 中公开沟通，不必每条消息都经过 PM 中转。

## 任务管理流程

### 创建任务（PM）
```bash
/Users/lin/Desktop/work/my-agent-teams/scripts/create-task.sh <task-id-title> "<title>" <assigned-agent> <domain> <project>
```
这会在 `/Users/lin/Desktop/work/my-agent-teams/tasks/<task-id>/` 下创建 `task.json`、`instruction.md`、`transitions.jsonl`。

### 派发任务（PM）
```bash
/Users/lin/Desktop/work/my-agent-teams/scripts/dispatch-task.sh /Users/lin/Desktop/work/my-agent-teams/tasks/<task-id>/task.json
```
- 将 `task.json.status` 改为 `dispatched`
- 通过 tmux send-keys 将任务发送给 `assigned_agent`

### 任务生命周期
```
pending → dispatched → working → ready_for_merge → merged → archived
```
- `pending`：任务已创建
- `dispatched`：已派发给 agent
- `working`：agent 写了 `ack.json` 后自动变更
- `ready_for_merge`：`result.json` + `verify` 通过后自动变更
- `failed / blocked / cancelled / timeout`：异常状态

### 任务目录结构
```
tasks/{task-id}/
├── task.json          # 任务定义（状态、分配、write_scope 等）
├── instruction.md     # PM 生成的纯任务指令
├── ack.json           # Agent 确认（agent 写）
├── result.json        # Agent 结果（agent 写）
├── verify.json        # 校验结果（watcher 写）
└── transitions.jsonl  # 状态变更日志（append-only）
```

### task.json 关键字段
- `id`：任务 ID
- `title`：任务标题
- `status`：当前状态
- `domain`：development / quality
- `assigned_agent`：唯一执行者
- `review_required`：是否需要审查
- `review_authority`：reviewer（审查者闭环）或 owner（林总工决策）
- `reviewer`：审查者 agent ID
- `test_required`：是否需要测试
- `write_scope`：允许修改的文件路径列表
- `project`：所属项目（chiralium / my-agent-teams）
- `depends_on`：依赖的任务 ID
- `blocks`：阻塞的任务 ID

### Agent 收到任务后
1. 读 `/Users/lin/Desktop/work/my-agent-teams/tasks/<task-id>/instruction.md` 了解任务详情。
2. 写 `/Users/lin/Desktop/work/my-agent-teams/tasks/<task-id>/ack.json` 确认收到。
3. 执行任务（只在 `write_scope` 范围内修改文件）。
4. 完成后写 `/Users/lin/Desktop/work/my-agent-teams/tasks/<task-id>/result.json`。
5. 如需审查，等待 reviewer 反馈。

## 环境隔离

- 开发目录：`~/Desktop/work/`
- 生产目录：`~/Desktop/prod/`
- 普通开发 agent 只能写 dev 目录
- 生产目录只有 PM 能触发部署操作
- `task.json.write_scope` 必须在项目 `dev_root` 内

## 配置

全局配置在 `/Users/lin/Desktop/work/my-agent-teams/config.json`，包含：
- `agents`：所有 agent 的角色、权限、tmux session、独立 workdir
- `projects`：项目注册表（`dev_root` / `prod_root`）
- `tasks_root` / `scripts_root` / `prompts_root` / `agents_root`：共享资源绝对路径
- `protected_paths`：保护路径列表
- `notifications`：飞书通知配置
