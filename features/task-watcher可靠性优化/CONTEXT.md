# CONTEXT：task-watcher 可靠性优化

> 初版由 arch-1 建立。目标：在不脱离当前 watcher / shell 脚本结构的前提下，明确影响范围、依赖关系、敏感区域和建议拆分。

## 1. 当前实现范围（基于现有结构）

### 1.1 直接主模块
- `scripts/task-watcher.sh`
  - 主轮询器
  - 扫描 `tasks/*/` 目录
  - 识别 `ack.json / result.json / review.md / design-review.md / verify.json` 变化
  - 自动推进状态流转与消息通知

### 1.2 强依赖脚本
- `scripts/send-to-agent.sh`
  - 负责向 tmux session 投递消息并做基础确认
- `scripts/close-task.sh`
  - 负责将 `ready_for_merge -> done` 自动收口
- `scripts/task-board-sync.py`
  - 负责把任务目录状态同步到 SQLite 看板
- `scripts/dispatch-task.sh`
  - 负责任务从 `pending -> dispatched` 的初始派发规则
- `scripts/verify.sh`
  - 负责结果工件结构校验，并生成 `verify.json`

### 1.3 相邻 watcher / 运行环境模块
- `scripts/tmux-watcher.sh`
  - 处理 tmux 内权限确认与自动 Enter
  - 不直接负责 task 状态流转，但会影响 watcher 相关脚本是否能持续运行

### 1.4 配置与状态目录
- `config.json`
  - agents/runtime/session/role 映射
  - project / domain policy / reviewer 规则
- watcher 运行时状态目录：
  - `STATE_DIR=/Users/lin/.openclaw/workspace/.task-watcher`
  - 当前主要保存“是否已通知”“上次时间戳”“签名”等去重状态
- watcher 锁目录：
  - `agents/arch-1/.watcher-lock`（当前仓库里可见）
- board / task 元数据目录：
  - `tasks/*/task.json`
  - `tasks/*/transitions.jsonl`
  - `dashboard/` 下 SQLite ingest 目标

---

## 2. 当前主链路与模块依赖关系

## 2.1 主状态流转链

```text
pending
  -> (dispatch-task / watcher auto-dispatch)
  -> dispatched
  -> ack.json 出现
  -> working
  -> result.json(status=done)
  -> ready_for_merge
  -> review pass
  -> verify pass
  -> close-task.sh
  -> done
```

## 2.2 `task-watcher.sh` 内部职责分层
1. **扫描层**
   - 轮询 `tasks/*/`
   - 读取 `task.json`
   - 跳过 `done/cancelled/archived`
2. **派发层**
   - `auto_dispatch_pending_arch()`
   - `auto_claim_pending_dev()`
3. **超时/重发层**
   - 对 `dispatched + 无 ack` 做超时检查
   - 当前只有“60 秒未 ack + 不在 Working pane 中”才重发
4. **状态推进层**
   - `ack.json -> working`
   - `result.json(done) -> ready_for_merge`
   - `review -> QA`
   - `verify(pass) -> close-task.sh`
5. **通知层**
   - `notify_pm / notify_agent / push_feishu`
6. **看板同步层**
   - `sync_task_board()`
   - `sync_if_changed()`
7. **幂等/去重层**
   - `STATE_DIR/*.flag`
   - `review_signature()` / mtime 记录

## 2.3 与其他脚本的依赖关系

```text
task-watcher.sh
  ├─ send-to-agent.sh      # 派发 / 重发 / reviewer / QA 通知
  ├─ close-task.sh         # QA pass 后自动收口
  ├─ task-board-sync.py    # 任何关键工件变化后同步看板
  ├─ config.json           # agent / reviewer / role / runtime 解析
  └─ tasks/* artifacts     # ack/result/review/design-review/verify/transitions
```

---

## 3. 当前可靠性问题与本轮优化对应点

## 3.1 进程级可靠性
### 现状
- `task-watcher.sh` 是一个无限循环 shell 进程
- 当前只有 `log()` 输出到 stdout
- 没有 heartbeat 文件
- 没有 watchdog 检查“进程还活着但循环卡死”的情况
- 没有脚本内自恢复或外层拉起协议

### 本轮目标落点
- heartbeat 文件：每轮或每 N 秒更新一次
- watchdog / supervisor：检测 heartbeat 超时或进程退出并重启
- 保持现有 shell 主体，不做 watcher 重写

## 3.2 日志持久化
### 现状
- `log()` 只 `echo` 到 stdout
- 重要事件（自动派发、重发、自动收口、review/QA 路由失败）没有可靠文件日志
- `transitions.jsonl` 只记录 task 状态，不覆盖 watcher 自身运行事件

### 本轮目标落点
- watcher 独立持久化日志文件
- 重要事件至少包含：
  - 自动派发
  - 超时重发
  - review/QA/close 路由
  - 外部脚本调用失败
  - watchdog 重启
- 7 天轮转，优先简单可维护方案

## 3.3 超时检测优化
### 现状
- 当前逻辑是：`dispatched` 超过 60 秒且无 ack 就尝试重发
- 通过 tmux pane grep `Working|• Working` 粗略区分 agent 是否正在工作
- 没有区分：
  - 真的没响应
  - agent 已收到但尚未写 ack
  - agent 正在处理中但 pane 文案不稳定
- 当前重发冷却为 300 秒，容易产生误报或无效噪声

### 本轮目标落点
- 采用任务状态 + 工件证据优先，而不是只看 tmux pane 文本
- 调整为：
  - 无 ack 且无 Working：超过 3 分钟才重发
  - Working 超过 30 分钟：通知 PM，不重发

---

## 4. 敏感区域（改动需特别小心）

## 4.1 `set_task_status()` 与 `transitions.jsonl`
- 这是任务生命周期的真实来源之一
- 任何重复写入、错误覆盖都会影响：
  - PM 判断
  - 看板同步
  - close-task 自动收口
- 不应在可靠性改造中改变其语义，只能增加外围保护

## 4.2 `result.json -> ready_for_merge -> review/QA/close` 自动链
- 当前自动流转已经覆盖 review / QA / close
- 可靠性优化不能改变现有触发条件顺序
- 尤其不能把日志落盘失败变成状态流转失败的硬阻塞点

## 4.3 `send-to-agent.sh` 的交互确认逻辑
- 当前依赖 tmux pane 内容变化与 regex
- 若重构过多，容易导致：
  - watcher 误判“已投递/未投递”
  - 超时策略与消息投递策略互相打架
- 第一批优化建议把“投递成功判断”视为现有前提，不在本批大改

## 4.4 `close-task.sh` 自动收口边界
- 只允许 `ready_for_merge -> done`
- 如果 watchdog / 重放逻辑错误重复触发 close，会导致状态污染
- 自动重试必须避免重复 close

## 4.5 `task-board-sync.py` / dashboard ingest
- watcher 当前会在多个工件 mtime 变化时触发 sync
- 若 heartbeat / 日志文件误纳入 sync 范围，会制造无意义同步噪声
- 第一批优化中，heartbeat/log 文件不应进入 board sync 触发链

---

## 5. 与现有自动流转/消息/收口/日志目录的耦合点

## 5.1 与自动流转的耦合点
- `ack.json` 决定 `dispatched -> working`
- `result.json(status=done)` 决定 `working -> ready_for_merge`
- `review.md + design-review.md` 决定是否通知 QA
- `verify.json` 决定是否自动收口或通知 PM

## 5.2 与 send-to-agent 的耦合点
- watcher 所有自动派发 / reviewer / QA / 超时重发都走 `send-to-agent.sh`
- 可靠性优化不能只看 watcher；重发策略必须兼容 send-to-agent 的 ack/timeout 行为

## 5.3 与 close-task 的耦合点
- watcher 并不直接改 `ready_for_merge -> done`
- 而是通过 `close-task.sh`
- 所以 watchdog / 自动重放必须避免重复触发 close 脚本

## 5.4 与日志/状态目录的耦合点
- 当前 `STATE_DIR` 已承担：
  - notified flags
  - review signature
  - resend timestamp
  - last selected dev state
- heartbeat / watchdog 状态如果继续写入同一目录，要避免命名冲突
- 建议将 heartbeat、pid、restart-cause 与 notified flags 分层命名

---

## 6. 建议的目录内共享约束

## 6.1 本功能第一批优化不做的事
- 不改 watcher 为 Python 常驻服务
- 不引入 fswatch/inotify
- 不重写 send-to-agent 的整体确认协议
- 不做通知重试/去重体系重构

## 6.2 第一批可接受的实现形态
- 继续以 `task-watcher.sh` 为主
- 允许新增一个轻量 watchdog shell 脚本
- 允许新增 watcher log 文件和 heartbeat/pid 文件
- 允许在现有 shell 内补充少量状态文件与时间计算

---

## 7. 建议拆分（按 execution 任务）

## 建议先后顺序
1. **先做进程可靠性 + heartbeat/watchdog**
2. **再做持久化日志**
3. **最后做超时检测优化**

原因：
- 没有 heartbeat / watchdog，就没有可靠观测基础
- 没有持久日志，超时误报很难复盘
- 超时策略优化依赖前两项提供的状态与日志证据

## 任务拆分建议

### Execution-1：task-watcher 进程级可靠性
**适合单独一个 execution 任务完成。**

目标：
- watcher 周期性写 heartbeat
- 引入 watchdog / 自动拉起协议
- 异常退出与卡死可被检测并重启

建议范围：
- `scripts/task-watcher.sh`
- 可新增 `scripts/task-watcher-watchdog.sh`（若 PM 允许追加 write_scope）
- 状态目录 heartbeat/pid/restart cause 文件

依赖：无，优先做

### Execution-2：task-watcher 持久化日志与 7 天轮转
**适合单独一个 execution 任务完成。**

目标：
- 重要事件写文件日志
- 实现 7 天保留
- 日志失败不阻塞主流转

建议范围：
- `scripts/task-watcher.sh`
- watcher 日志目录约定
- 可能需要一个轻量 log rotate helper

依赖：最好依赖 Execution-1

### Execution-3：超时检测优化
**建议单独一个 execution 任务完成。**

目标：
- 调整 dispatched 无 ack 重发阈值到 3 分钟
- 区分“无响应”和“Working 中”
- Working 超过 30 分钟通知 PM，不重发

建议范围：
- `scripts/task-watcher.sh`
- 若需要，少量增强 `send-to-agent.sh` 的可观察性字段，但不大改协议

依赖：建议依赖 Execution-1 和 Execution-2

## 不建议合并成一个 execution 的情况
如果把 1/2/3 三项一次性交给一个 execution：
- 风险太高
- 不利于快速定位“可靠性问题是进程级、日志级还是超时策略级”
- 也不利于 QA 分批验证

因此建议 **至少拆成 3 个 execution 任务**。

---

## 8. PM 拆任务时的建议

### 建议先做
- 进程级可靠性（heartbeat + watchdog）
- 日志持久化

### 建议后做
- 超时检测策略优化

### 推荐依赖关系
```text
Execution-1 进程可靠性
  -> Execution-2 日志持久化
  -> Execution-3 超时策略优化
```

也可接受：
```text
Execution-1 进程可靠性
Execution-2 日志持久化
  -> Execution-3 超时策略优化
```

前提是 Execution-3 必须在前两者至少有一项完成后再做。

---

## 9. 当前建议摘要
- 第一批优化应继续基于现有 shell watcher 架构演进，不应脱离现有脚本结构空想重构
- 最敏感的是 `set_task_status / transitions.jsonl / result->review->QA->close` 主链路，不能被可靠性改造破坏
- 最合理的拆法是 3 个 execution：
  1. 进程级可靠性
  2. 日志持久化
  3. 超时检测优化
- 先做 heartbeat/watchdog，再做日志，再做超时策略
