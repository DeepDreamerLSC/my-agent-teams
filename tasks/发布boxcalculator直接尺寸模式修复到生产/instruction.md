# 任务：发布 box-calculator 直接尺寸模式修复到生产

## 背景
林总工已明确要求：直接安排架构师把已完成的 box-calculator 增强发布到生产。

当前应吸收的**有效任务结果**：
- `/Users/lin/Desktop/work/my-agent-teams/tasks/增强boxcalculator支持直接输入鞋盒尺寸`
- `/Users/lin/Desktop/work/my-agent-teams/tasks/修正boxcalculator历史总数回填回归`

说明：
- 较早的“紧急修复生产外箱尺寸计算直接尺寸输入模式”与“修正boxcalculator数量兜底解析回归”已被后续补修吸收，不应再单独作为发布内容。
- 更早的“两列混装优化 + 长宽交换”已在上一轮 commit `bb3dde3dad8c8ef8990a1f2c80739721c5d2de7f` 发布，本次只补**新增的直接尺寸输入模式与 recent_messages 回填回归修复**。

## 你的任务
### A. 整理并合入本次 box-calculator 有效改动
仅发布以下 box-calculator 相关变更：
- `skills/custom/box-calculator/1.0.0/skill.py`
- `skills/custom/box-calculator/1.0.0/SKILL.md`
- `backend/tests/test_box_calculator_skill.py`

### B. 更新 Release Note
在：
- `/Users/lin/Desktop/work/chiralium/design/product/release-note.md`

补充 2026-04-28（或当前最新日期）一条简洁更新，说明：
- 外箱尺寸计算已支持“直接输入鞋盒实际尺寸 + 数量”模式
- 同时修复了历史总数回填导致的混装回归问题

### C. 提交并推送
- `git add`
- `git commit`
- `git push origin master`

### D. 部署生产
执行：
```bash
cd /Users/lin/Desktop/work/chiralium && ./scripts/deploy.sh prod
```

## 发布边界
- 不要夹带当前工作树中的无关 AI 对话 provider 相关修改
- 只整理 box-calculator 本次新增有效改动

## 交付物
完成后写：
- `/Users/lin/Desktop/work/my-agent-teams/tasks/发布boxcalculator直接尺寸模式修复到生产/result.json`

请在 result.json 中包含：
- release_note_path
- commit_hash
- pushed
- deployed_commit
- health_check_result
- included_files
- remaining_unrelated_changes
