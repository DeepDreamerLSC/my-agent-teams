# 任务：实现PPT精美模式入口与CogView页图渲染Demo

## 任务类型
开发

## 目标
在现有 `ppt_generator` skill 中新增 **polished / 精美模式** 的入口，并用 **CogView-3-Flash** 跑通“文本规划 → 逐页图像渲染”的 demo 主链路。

## 任务边界
- 本任务只负责：
  1. `ppt_generator` 的 polished 模式入口
  2. `presentation_plan` 扩展 schema
  3. 普通内容页 / 封面页 / 收尾页的图像渲染 demo
- 不负责 PPTX 图片页装配（由并行任务处理）。
- 不做图表页结构化渲染。
- 不做独立页面。

## 输入事实
- 已确认方案文档：`design/product/ppt-skill-image-mode-upgrade-plan.md`
- 方向：继续作为 skill 集成，不做独立页面。
- Demo 目标：先用 `CogView-3-Flash` 跑 3~5 页最小闭环，验证图像页效果。
- 推荐最小页型：`cover / content / closing`

## 约束
- write_scope:
  - `skills/custom/ppt_generator/1.0.0/skill.py`
  - `skills/custom/ppt_generator/1.0.0/manifest.json`
  - `backend/app/services/ppt_page_render_service.py`
  - `backend/tests/test_ppt_generator_skill.py`
  - `backend/tests/test_ppt_page_render_service.py`
- read_only: false
- target_environment: dev
- execution_mode: dev
- owner_approval_required: false
- 必须继续复用现有 skill 输入输出契约（`parsed_files` / `recent_messages` / `display_type=file`）
- 图像模型先用 CogView-3-Flash，不直接接 GLM-Image
- 只做 demo 闭环，不追求生产级完整性

## 交付物
- polished 模式入口
- `presentation_plan` 扩展 schema
- 页图渲染 service
- 至少一组测试，证明：
  1. polished 模式能生成 page plan
  2. 可调用 CogView-3-Flash 逐页渲染 page image
- `result.json`

## 验收标准
1. `ppt_generator` 可以区分 `simple` / `polished` 两种模式入口。
2. polished 模式下，能得到至少 cover/content/closing 三类页的页面渲染结果。
3. 页图渲染逻辑被抽成独立 service，不要把 provider 调用散落在 skill 里。
4. 测试通过，并在 `result.json` 中说明 demo 当前支持的页型、页数限制、调用模型。

## 下游动作
review
