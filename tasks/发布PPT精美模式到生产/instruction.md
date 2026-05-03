# 任务：发布PPT精美模式到生产

## 任务类型
部署

## 目标
将已完成开发、QA、并已整理为集成基线的 **PPT 精美模式（polished）最终 `.pptx` 闭环** 发布到 chiralium 生产环境。

## 任务边界
- 本任务负责：
  1. 确认当前待发布 commit 范围
  2. 更新 Release Note
  3. 推送远端（如仍有未推送提交）
  4. 执行生产部署
  5. 做最小生产验证
- 不再追加新功能开发。
- 不夹带无关 AI 对话 / 其他 feature 改动。

## 输入事实
- 林总工已明确要求：安排部署。
- 上游集成基线任务：`合入PPT精美模式最终闭环到集成` 已完成。
- 当前应上线的核心能力：
  1. `ppt_generator` 支持 `simple / polished` 双模式入口
  2. `presentation_plan`
  3. `CogView-3-Flash` 逐页图像渲染
  4. 图片页装配能力
  5. `polished` 最终返回 `.pptx`，不再只是 zip demo 包
- 相关代码已在 `origin/master` 的独立集成提交中整理完成。

## 约束
- write_scope: []
- read_only: false
- target_environment: prod
- execution_mode: deploy
- owner_approval_required: true
- owner_approved_by: 林总工
- owner_approved_at: 2026-05-01T13:22:11+08:00
- 部署执行者：arch-1
- 部署统一走项目脚本，不自行拼接生产命令。

## 交付物
- Release Note 更新结果
- 最终发布 commit hash
- 生产部署结果
- 最小验证结果
- `result.json`

## 验收标准
1. 生产部署命令已执行：
   ```bash
   cd /Users/lin/Desktop/work/chiralium && ./scripts/deploy.sh prod
   ```
2. Release Note 已更新，至少说明：
   - PPT 精美模式 polished demo 闭环上线
   - polished 最终 `.pptx` 输出能力
3. 主站健康检查通过。
4. 后端健康检查通过。
5. `result.json` 中写清：
   - 最终 commit hash
   - 部署结果
   - 生产验证结果
   - 是否有遗留风险

## 下游动作
deploy
