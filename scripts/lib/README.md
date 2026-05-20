# scripts/lib

`lib/` 存放 scripts 顶层入口复用的模块代码。顶层入口路径保持兼容，新增或拆出的业务逻辑优先放入这里。

## Python 模块

- `task_artifacts.py`：任务产物读取、摘要与原子写入工具。
- `task_pool_rules.py`：任务池/预留/认领规则。
- `task_quality_rules.py`：质量闸门规则。
- `task_state_invariants.py`：任务状态不变量检查。
- `task_workspace.py`：任务工作区/worktree 解析。

## Bash 模块

- `task_watcher_notifications.sh`：`task-watcher.sh` 的 PM/agent 通知、飞书推送与系统 chat 事件函数。

## 维护约定

- Bash 模块只定义函数和轻量常量，不应自行启动 watcher 主循环。
- Bash 模块依赖的变量/函数必须在文件头注释中列明。
- Python 模块新增后应纳入 `python3 -m py_compile scripts/lib/*.py` 校验。
