# 任务：发布PPT生成skill到生产

## 任务类型
部署

## 目标
将已完成并通过 review/QA 的 PPT 生成 skill 相关改动整理为集成提交，推送到 `origin/master`，随后部署到生产环境。

## 任务边界
- 本任务负责：
  1. 合入 / 整理 PPT 生成 skill 相关改动
  2. 更新 Release Note
  3. 推送远端
  4. 部署生产
  5. 最小验证
- 不扩展新功能，不再追加开发任务。

## 输入事实
- 林总工已明确确认：继续安排合入到集成分支，然后部署到生产环境。
- 已完成并收口的上游任务：
  1. `实现PPT生成skill文档主链路`
  2. `收口PPT生成skill图片OCR消费闭环`
- 当前能力已包括：
  - 文档 / PDF → 解析内容 → 生成 `.pptx`
  - 图片 → OCR / `parsed_files` → `ppt_generator` 消费 → 生成 `.pptx`
  - skill 形态与现有 skill 体系一致

## 约束
- target_environment: prod
- execution_mode: deploy
- owner_approval_required: true
- owner_approved_by: 林总工
- owner_approved_at: 2026-04-30T17:02:43+08:00
- 部署执行者：arch-1
- 只纳入本次 PPT 生成 skill 链路所需改动，避免夹带无关修改

## 交付物
- 集成提交（commit hash）
- Release Note 更新
- 推送结果
- 生产部署结果
- 最小验证结果
- `result.json`

## 验收标准
1. PPT 生成 skill 相关改动已整理为干净的集成提交，并推送到 `origin/master`。
2. Release Note 已更新，至少写清：
   - 新增 PPT 生成 skill
   - 文档/PDF 主链路
   - 图片 OCR 消费闭环
3. 已执行生产部署：
   ```bash
   cd /Users/lin/Desktop/work/chiralium && ./scripts/deploy.sh prod
   ```
4. 最小验证通过：
   - 主站健康 OK
   - 后端健康 OK
   - skill 至少在配置/发现层面可见
5. `result.json` 中写清最终提交 hash、部署结果、验证结果、是否有遗留风险。

## 下游动作
deploy
