# Code Review - 切换PPT生成默认精美模式

## 结论
- **审查结论：驳回（REQUEST CHANGES）**
- 依据：`instruction.md`、`result.json`、`ppt_generator` skill 与相关测试代码审查。
- 说明：任务目录当前 **无 `verify.json`**；本次结论基于代码与工件审查给出，未自行执行功能测试。

## 通过项
- 默认模式判定已从“默认 simple”切到“默认 polished”：
  - `/Users/lin/Desktop/work/chiralium/skills/custom/ppt_generator/1.0.0/skill.py:127-134`
- 显式 `render_mode=simple` / `mode=simple` 仍保留：
  - `/Users/lin/Desktop/work/chiralium/skills/custom/ppt_generator/1.0.0/skill.py:127-130`
- manifest 中 `default_render_mode` 与描述文案已同步：
  - `/Users/lin/Desktop/work/chiralium/skills/custom/ppt_generator/1.0.0/manifest.json:1-17`

## 阻塞问题

### 1. 默认切到 polished 后，普通请求会无条件依赖 CogView 页图渲染；当图片模型未就绪时将直接失败，存在全局行为回归风险
- 位置：
  - `/Users/lin/Desktop/work/chiralium/skills/custom/ppt_generator/1.0.0/skill.py:74-84,127-134`
  - `/Users/lin/Desktop/work/chiralium/backend/app/services/ppt_page_render_service.py:62-64`
- 当前逻辑是：
  1. 只要调用方没有显式传 `simple`
  2. 就默认进入 `polished`
  3. 然后立刻调用 `render_presentation_demo()`
- 但 `render_presentation_demo()` 在没有可用 CogView 图片模型时会直接抛错：
  - `raise RuntimeError("当前没有可用的 CogView 图片生成模型，无法运行精美模式 demo")`
- 这意味着：
  - 之前“普通 PPT 请求”至少还能走 simple 文本导出主链路；
  - 现在默认被切到 polished 后，**会对 CogView 可用性形成强依赖**；
  - 而本任务说明里又明确写了“**不负责 CogView 密钥/模型解析修复（并行任务处理）**”，说明该依赖并未在本任务内被兜住。
- 影响：这是对默认用户路径的全局行为切换，若并行环境修复未同步到位，普通 PPT 请求会直接失败，属于阻塞问题。

## 测试问题

### 2. 缺少“默认 polished 但图片模型不可用”场景测试，无法证明本次行为切换在非理想环境下仍可接受
- 位置：
  - `/Users/lin/Desktop/work/chiralium/backend/tests/test_ppt_generator_skill.py:56-245`
- 当前测试已覆盖：
  - 默认进入 polished
  - 显式 simple 保持 simple
- 但未覆盖：
  - `render_presentation_demo()` 报 “无可用 CogView 模型” 时，skill 是否有合理降级或明确可接受的失败契约
- 对于这种“切默认值、影响所有普通请求”的改动，这个缺口过大。

## 最终意见
这次改动把默认入口切到了 polished，但**没有同时处理 polished 对 CogView 可用性的强依赖**。在并行任务未一起收口前，这会让普通 PPT 请求从“可导出 simple”变成“默认可能直接失败”。建议在补齐依赖关系（或增加安全降级策略）并补上对应测试前，暂不合入。
