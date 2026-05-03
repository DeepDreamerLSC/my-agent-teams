# 任务：修正PPT精美模式Demo归档截断与CogView约束

## 任务类型
开发

## 目标
根据 `实现PPT精美模式入口与CogView页图渲染Demo` 的 review 驳回意见，做最小范围补修，解决两个阻塞问题：
1. polished demo zip 包中的 `presentation_plan.json` 不得再通过“按字节硬截断”方式写入，必须保证它始终是合法 UTF-8 且可解析的 JSON。
2. polished demo 的图像模型选择必须严格受限于 **CogView-3-Flash / cogview-3** 路径，不能因显式 `image_model_id` 覆盖而绕过当前 demo 阶段的模型边界。

## 任务边界
- 这是 review 驳回后的补修任务，只修阻塞项，不扩展新能力。
- 不负责 PPTX 图片页装配。
- 不负责图表页结构化渲染。
- 不做独立页面。

## 输入事实
- 上游任务：`实现PPT精美模式入口与CogView页图渲染Demo`
- review 结论：`/Users/lin/Desktop/work/my-agent-teams/tasks/实现PPT精美模式入口与CogView页图渲染Demo/review.md`
- review 明确的两个阻塞点：
  1. `presentation_plan.json` 可能被字节截断，导致 JSON / UTF-8 损坏。
  2. 显式 `image_model_id` 会绕过 CogView 限制，与 demo 约束不一致。

## 约束
- write_scope:
  - `skills/custom/ppt_generator/1.0.0/skill.py`
  - `backend/app/services/ppt_page_render_service.py`
  - `backend/tests/test_ppt_generator_skill.py`
  - `backend/tests/test_ppt_page_render_service.py`
- read_only: false
- target_environment: dev
- execution_mode: dev
- owner_approval_required: false
- 必须保持 demo 边界：当前阶段只允许 CogView 路线，不提前接 GLM-Image。
- 必须补测试，证明两个阻塞点已解决。

## 交付物
- 代码补修
- 测试补齐
- `result.json`

## 验收标准
1. zip 包中的 `presentation_plan.json` 始终为合法 UTF-8 与可解析 JSON；禁止按字节硬截断造成损坏。
2. 传入非 CogView 的 `image_model_id` 时，必须被拒绝或纠正到当前 demo 合法模型边界，不能静默绕过。
3. 新增/更新测试覆盖上述两点。
4. 不误伤原有 polished demo 主链路与 simple 模式。

## 下游动作
review
