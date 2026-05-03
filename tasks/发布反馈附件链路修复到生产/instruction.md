# 任务：发布反馈附件链路修复到生产

## 背景
林总工已指示：反馈管理的三个修复任务开发已完成，请安排：
1. 更新 ReleaseNote
2. 合入代码、提交推送
3. 部署到生产环境

当前相关链路：
- 已完成并通过：
  - `/Users/lin/Desktop/work/my-agent-teams/tasks/补齐反馈附件详情契约与元数据返回`
  - `/Users/lin/Desktop/work/my-agent-teams/tasks/收束反馈附件详情为可靠下载入口`
- 仍需先补齐 review / QA：
  - `/Users/lin/Desktop/work/my-agent-teams/tasks/补齐反馈AI链路附件元数据传递`

## 你的任务
在上游任务全部通过后，统一完成：

### A. 更新 Release Note
在：
- `/Users/lin/Desktop/work/chiralium/design/product/release-note.md`

补充反馈管理附件链路相关更新，要求简洁、一行一条。

### B. 合入 / 提交 / 推送
仅整理本次反馈管理附件链路相关改动，不夹带当前工作树中无关的 AI 对话 provider 相关修改。

### C. 部署生产
执行：
```bash
cd /Users/lin/Desktop/work/chiralium && ./scripts/deploy.sh prod
```

## 说明
- 当前任务先创建排队，等最后一个子任务（AI 附件元数据传递）通过 review/QA 后再正式执行
- 生产部署已由林总工明确批准

## 交付物
完成后写：
- `/Users/lin/Desktop/work/my-agent-teams/tasks/发布反馈附件链路修复到生产/result.json`

result.json 至少包含：
- release_note_path
- commit_hash
- pushed
- deployed_commit
- health_check_result
- included_files
- remaining_unrelated_changes
