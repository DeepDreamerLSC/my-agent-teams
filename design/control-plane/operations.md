# 运维与故障恢复

## 日常检查

```bash
python3 scripts/control-plane.py project list
python3 scripts/control-plane.py overview
python3 scripts/control-plane.py session list --project-id billing-service
scripts/teamctl.sh doctor
```

后台“控制面”视图显示项目、需求阶段、任务数量、backend、会话健康、最后活动、门禁和 Owner 决策。`unknown` 表示没有足够证据，`offline` 表示心跳过期或后端明确离线，`unsupported` 表示后端不提供该能力。

## 故障分类

- `unknown`：检查 `last_seen_at`、控制面 API、Hook 网络和项目 manifest；不要直接重派任务。
- `offline`：先确认执行面 worktree 和会话，再决定恢复或转派；所有动作写事件。
- `unsupported`：安装/配置官方 Codex App Server bridge 或继续使用 tmux；不要伪造在线状态。
- `out_of_order_sequence`：上游重试或乱序，事件已保留但未应用；检查上游序列号。
- `repeated_gate_failure`：同一阶段三次驳回，Owner 收件箱会提供范围、取消、继续返工选项。

## 恢复规则

1. 先保留 SQLite、项目 `git diff`、任务目录和 backend 日志。
2. 不覆盖业务项目未提交修改，不自动执行生产部署。
3. 重试事件必须复用原 `idempotency_key`；新尝试使用递增 sequence。
4. 重新绑定已有会话前先确认 project/root/worktree/branch，跨项目绑定会被拒绝。
5. schema 错误先备份，再执行迁移或恢复兼容版本；不要删除旧任务事实源。

## Codex bridge 检查

```bash
codex app-server daemon version
codex app-server generate-json-schema --experimental --out /tmp/codex-app-server-schema
```

只把官方 App Server/SDK bridge 的可验证结果写入会话事件。若 bridge 未配置、认证失败或返回不完整结果，后台应显示 `unsupported` 或 `unknown`，而不是根据 Desktop UI、私有数据库或 transcript 猜测在线状态。
