# 任务：分析banana-slides并设计PPT精美模式升级方案

## 任务类型
方案

## 目标
分析 banana-slides 的代码架构与页面渲染思路，结合 chiralium 当前已上线的 `ppt_generator` skill，输出一份“PPT 精美模式（图像生成模式）升级方案”，并明确如何先用 **CogView-3-Flash** 做 demo 验证效果。

## 任务边界
- 本任务以**架构分析 / 集成方案设计**为主，不直接落业务代码。
- 重点是评估如何把“图像生成渲染每页 PPT”的思路嫁接到现有 **skill 体系** 中。
- 不要把方案导向“单独做一个新功能页面”；应继续围绕 skill 体系设计。
- 不直接拆执行子任务；你需要在方案里给出建议拆解，PM 后续会在林总工确认后再派发。

## 输入事实
- 需求：按用户需求生成 PPT 的功能，现已以 `ppt_generator` skill 形态上线简洁模式（标题 + 要点列表）。
- 林总工反馈：当前格式太简单，需要升级更精美的 PPT 输出能力。
- 调研参考：
  1. banana-slides（GitHub 14.3k⭐）
     - 核心思路：用 AI 图像生成模型直接渲染每一页 PPT（背景+文字+图表+排版合成在一张图里）
     - 效果最好，但每页都要调图像生成 API
     - 参考：`https://github.com/Anionex/banana-slides`
  2. AiPPT / 文多多
     - 可参考 JSON schema / 渲染思路，但后端闭源，不作为主集成对象
- 林总工已明确方向：
  - 参考 banana-slides 的图像生成思路
  - 不用 nano banana pro
  - 优先采用**智谱图像生成模型**：
    - 验证阶段：`CogView-3-Flash`
    - 生产阶段：`GLM-Image`
  - 数据图表页仍可用 python-pptx 渲染真实图表
  - 内容页考虑图像生成
  - 用户可选择：`简洁模式`（当前方案）/ `精美模式`（图像生成）
- 当前仓库上下文：
  - `ppt_generator` skill 已在生产上线
  - 文档/PDF 与图片 OCR 消费闭环已打通
  - 图像生成模型与聊天/skill 体系已有基础能力可参考

## 约束
- write_scope: `design/product/ppt-skill-image-mode-upgrade-plan.md`
- read_only: false
- 依赖上游任务: 无
- target_environment: dev
- execution_mode: dev
- owner_approval_required: false
- 方案必须围绕“**作为 skill 集成**”展开
- 必须明确指出：
  1. 哪些部分复用当前 `ppt_generator`
  2. 哪些部分需要新增模式 / provider / renderer / prompt schema
  3. demo 阶段最小闭环是什么

## 交付物
- 一份方案文档：`/Users/lin/Desktop/work/chiralium/design/product/ppt-skill-image-mode-upgrade-plan.md`
- `result.json`，至少包含：
  1. banana-slides 架构拆解结论
  2. 对 chiralium 的集成建议
  3. demo 最小闭环建议
  4. 建议拆解的执行任务（dev-1 / dev-2 分工建议）
  5. 风险与成本判断

## 验收标准
1. 方案文档清楚解释 banana-slides 的关键架构，不只是泛泛概述。
2. 能明确说明如何在现有 `ppt_generator` skill 基础上扩展出“精美模式”。
3. demo 路线必须具体到：输入、模型、输出、与现有 skill 体系的接入点。
4. 方案中要区分：
   - demo 阶段（CogView-3-Flash）
   - 生产阶段（GLM-Image）
5. 方案完成后，PM 能据此向林总工推飞书确认，并据此拆执行子任务。

## 下游动作
方案完成后飞书确认并拆子任务
