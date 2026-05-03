# 任务：同步 box-calculator 修复到仓库并部署生产

## 背景
林总工已明确批准部署 box-calculator 相关改动到生产。
上游任务：
- `/Users/lin/Desktop/work/my-agent-teams/tasks/修改boxcalculator支持混装两列优化`

注意：上游任务修改的是本地 skill 定义参考路径：
- `/Users/lin/.agents/skills/box-calculator/SKILL.md`

而 chiralium 项目中真正随仓库/生产发布的 skill 位于：
- `/Users/lin/Desktop/work/chiralium/skills/custom/box-calculator/1.0.0/SKILL.md`

因此本次部署前，你需要先把已通过 review + QA 的规则变更**同步到 chiralium 仓库中的 skill 文件**，再更新 release note、提交推送、部署生产。

## 你的任务
### A. 同步已通过的 skill 规则变更到仓库
将已确认通过的 box-calculator 规则同步到：
- `/Users/lin/Desktop/work/chiralium/skills/custom/box-calculator/1.0.0/SKILL.md`

必须覆盖的改动：
1. 混装两列时强制启用左右列优化
2. `内宽 = 左列最大宽度 + 右列最大宽度`
3. 统一列高 = max(H)，内高 = max(L)
4. 外箱长宽交换规则（外宽 > 外长时交换）
5. 示例与输出说明同步更新

### B. 更新 release note
在：
- `/Users/lin/Desktop/work/chiralium/design/product/release-note.md`

补一条简洁的一行更新，说明外箱尺寸计算能力已支持混装两列优化与长宽交换。

### C. git add / commit / push
整理本次应发布的 box-calculator 相关改动：
- git add
- commit message 写清楚
- push 到 `origin/master`

### D. 部署生产
执行：
```bash
cd /Users/lin/Desktop/work/chiralium && ./scripts/deploy.sh prod
```

## 验收标准
1. 仓库内 skill 文件已同步最新规则
2. release-note 已更新
3. commit 已 push 到远端
4. 生产部署完成且健康检查通过

## 交付物
完成后写：
- `/Users/lin/Desktop/work/my-agent-teams/tasks/同步boxcalculator修复到仓库并部署生产/ack.json`
- `/Users/lin/Desktop/work/my-agent-teams/tasks/同步boxcalculator修复到仓库并部署生产/result.json`

result.json 请包含：
- synced_skill_path
- release_note_path
- commit_hash
- pushed
- deployed_commit
- deploy_command
- health_check_result
- remaining_unrelated_changes
