# 任务：扩展PPTX装配器支持图片页插入

## 任务类型
开发

## 目标
扩展 chiralium 现有 PPTX 装配能力，使后端能把“整页渲染好的图片页”插入最终 `.pptx`，为 PPT 精美模式 demo 提供装配基础。

## 任务边界
- 本任务只负责 PPTX 装配器层。
- 不负责图像生成调用本身。
- 不负责图表页结构化渲染。
- 不改独立页面。

## 输入事实
- 已确认方案：普通内容页将由图像模型渲染为整页视觉图，然后装配进 `.pptx`。
- 当前 `office_export_service.py` 只支持结构化标题 + bullets 的 PPTX 生成。
- Demo 阶段至少需要支持把 cover/content/closing 的页面图插入到 PPTX。

## 约束
- write_scope:
  - `backend/app/services/office_export_service.py`
  - `backend/tests/test_ppt_image_page_assembly.py`
- read_only: false
- target_environment: dev
- execution_mode: dev
- owner_approval_required: false
- 不引入新的页面/UI
- 以“最小可运行 demo 装配能力”为目标，不先追求复杂动画

## 交付物
- 图片页装配能力
- 测试，至少证明：
  1. 给定页图后，能生成可打开的 `.pptx`
  2. 与现有结构化 PPTX 生成能力不冲突
- `result.json`

## 验收标准
1. 后端可以把整页图片插入 PPTX，形成 demo 可展示的页面。
2. 不误伤现有简洁模式的 `.pptx` 输出。
3. 测试通过，并在 `result.json` 中说明当前图片页装配能力的边界。

## 下游动作
review
