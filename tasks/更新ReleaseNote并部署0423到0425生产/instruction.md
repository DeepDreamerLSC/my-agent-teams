# 任务：更新 Release Note、提交推送并部署 4/23-4/25 生产变更

## 背景
林总工已明确下令执行本次生产发布，要求：
1. 把最近三天（4/23-4/25）的主要更新写到 release note 里，简洁，一行一条
2. `git add / commit / push`
3. 执行生产部署：
   - `cd /Users/lin/Desktop/work/chiralium && ./scripts/deploy.sh prod`

当前仓库存在待提交变更，请你以**当前工作树中本次计划发布的最终有效改动**为准，统一整理后发布。

当前 release note 文件：
- `/Users/lin/Desktop/work/chiralium/design/product/release-note.md`

## 你的任务
### A. 更新 release note
- 在 `release-note.md` 中补充 2026-04-23、2026-04-24、2026-04-25 三天的主要更新
- 要求：**简洁，一行一条**
- 只写用户/运营能感知的主要变化，不写实现细节

### B. 整理并提交代码
- 检查当前 `git status`
- `git add` 本次应该发布的改动
- 写好 commit message
- `git push` 到远端 `master`

### C. 生产部署
- 执行：
  - `cd /Users/lin/Desktop/work/chiralium && ./scripts/deploy.sh prod`
- 脚本执行时间较长，请耐心等待完成

## 发布边界
- 你同时承担集成与部署职责，可以直接完成上述三步
- 允许吸收当前已在推进中的 DeepSeek / GLM 相关有效改动，但不要夹带明显无关变更
- 若发现某些未提交文件不应进入本次发布，请在 result.json 中明确列出并说明原因

## 交付物
完成后写：
- `/Users/lin/Desktop/work/my-agent-teams/tasks/更新ReleaseNote并部署0423到0425生产/ack.json`
- `/Users/lin/Desktop/work/my-agent-teams/tasks/更新ReleaseNote并部署0423到0425生产/result.json`

请在 `result.json` 中包含：
- release_note_path
- release_note_entries_summary
- commit_hash
- pushed (true/false)
- deployed_commit
- deploy_command
- health_check_result
- remaining_unrelated_changes
