# Code Review - 实现PPT精美模式入口与CogView页图渲染Demo

## 结论
- **审查结论：驳回（REQUEST CHANGES）**
- 依据：`instruction.md`、`result.json`、`ppt_generator` skill、`ppt_page_render_service` 与相关测试代码审查。
- 说明：任务目录当前 **无 `verify.json`**；本次结论基于代码与工件审查给出，未自行执行功能测试。

## 通过项
- `ppt_generator` 已新增 `simple / polished` 两种模式入口：
  - `/Users/lin/Desktop/work/chiralium/skills/custom/ppt_generator/1.0.0/skill.py:69-125`
- 页图渲染逻辑已抽成独立 `ppt_page_render_service`，没有把 provider 调用散落回 skill：
  - `/Users/lin/Desktop/work/chiralium/backend/app/services/ppt_page_render_service.py:53-112,115-176`
- `cover / content / closing` 三类页型的最小 demo 主链路与测试已补出：
  - `/Users/lin/Desktop/work/chiralium/backend/tests/test_ppt_page_render_service.py:13-52`
  - `/Users/lin/Desktop/work/chiralium/backend/tests/test_ppt_generator_skill.py:98-158`

## 阻塞问题

### 1. `presentation_plan.json` 会被按字节硬截断，可能生成无效 JSON / 无效 UTF-8，破坏 polished demo 包契约
- 位置：
  - `/Users/lin/Desktop/work/chiralium/skills/custom/ppt_generator/1.0.0/skill.py:30,317-323`
- 当前实现会：
  - 先把 `plan` 序列化成 `plan_bytes`
  - 再直接写入 `plan_bytes[:_MAX_DEMO_ARCHIVE_PLAN_BYTES]`
- 问题在于：
  1. 这是**按字节硬截断**，不是按 JSON 字段级裁剪；
  2. 可能把中文多字节字符截断在中间，导致 `presentation_plan.json` 不是合法 UTF-8；
  3. 也可能把 JSON 结构直接截断坏，导致 demo 包内的 `presentation_plan.json` 无法被下游读取。
- 影响：本任务把 zip demo 包定义为 polished 模式的核心交付物之一，`presentation_plan.json` 又是该 demo 包中的关键工件；当前实现存在直接产出损坏工件的风险，属于阻塞问题。

### 2. 显式 `image_model_id` 会绕过 CogView 限制，和任务要求“先用 CogView-3-Flash，不直接接 GLM-Image”不一致
- 位置：
  - `/Users/lin/Desktop/work/chiralium/skills/custom/ppt_generator/1.0.0/skill.py:78-83`
  - `/Users/lin/Desktop/work/chiralium/backend/app/services/ppt_page_render_service.py:82-94`
- 当前 `ppt_generator` 会把 `params.image_model_id` / `context.selected_image_model_id` 直接传给 `render_presentation_demo()`。
- 但 `_resolve_demo_image_model()` 的实现是：
  - 只要传入的 `image_model_id` 对应的是**任意活跃的 image_generation 模型**，就直接返回；
  - **不会再校验它是不是 zhipu / CogView-3-Flash / cogview-3**。
- 这与任务约束里的：
  - “图像模型先用 CogView-3-Flash”
  - “不直接接 GLM-Image”
  不一致。
- 影响：当前 demo 实际上允许被任意 image model 覆盖，和任务要求的 provider/model 边界不一致，且测试未覆盖该路径。

## 测试问题
- 位置：
  - `/Users/lin/Desktop/work/chiralium/backend/tests/test_ppt_generator_skill.py:98-158`
  - `/Users/lin/Desktop/work/chiralium/backend/tests/test_ppt_page_render_service.py:13-100`
- 当前测试已覆盖：
  - polished 模式会返回 zip demo 包
  - 页图渲染 service 会调用 CogView 接口
- 但未覆盖：
  1. zip 内 `presentation_plan.json` / `rendered_pages.json` 是否始终为**可解析的有效 JSON**；
  2. 传入非 CogView 的 `image_model_id` 时是否会被拒绝或纠正。
- 因此测试还不足以兜住上面的两个阻塞点。

## 最终意见
当前实现已经把 polished demo 的主链路搭起来了，但还存在两个阻塞问题：
1. demo 包中的 `presentation_plan.json` 可能被截断损坏；
2. 显式 `image_model_id` 会绕过 CogView 限制。

在修正这两点并补上对应测试前，暂不建议合入。
