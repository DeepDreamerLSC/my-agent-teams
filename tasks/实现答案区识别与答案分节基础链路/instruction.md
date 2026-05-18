# 任务：实现答案区识别与答案分节基础链路，打破 0/5 现状

## 任务类型
development

## 目标
在现有 Exercise IR / assembler 基础上，补齐 **答案区识别与 `AnswerSection` 物化** 的基础链路，让当前具有明显答案线索的样例不再长期停留在 `answer_area=0/5`、`answer_section=0/5`，同时保证 student 正文顺序不回归。

## 任务边界
- 本任务优先解决“识别并保留下来”，不是一次性做完完整教师版产品能力。
- 不改变默认发布边界，不触碰 hybrid 发布触发逻辑。
- 不允许为了生成答案分节而破坏现有题号顺序、题干/选项/材料、图片/表格插入结果。
- 对无法可靠归属的答案内容，要保留 warning 或未匹配信息，不能静默丢弃。

## 输入事实
- 当前正式 evidence 仍是：`answer_area=0/5`、`answer_section=0/5`。
- 现有代码中：
  - `exercise_ir.py` 已有 `AnswerSection` / `AnswerArea` 结构；
  - `exercise_docx_assembler.py` 已支持渲染 answer sections；
  - `exercise_detector.py` 已有少量 answer_area hint 逻辑，但真实样例未形成稳定输出。
- P1 文档已明确：答案/教师版是当前最核心的质量缺口之一。

## 约束
- `write_scope` 以 `task.json` 为准。
- 必须优先复用当前 IR / detector / assembler 结构，不要新起一套平行数据结构。
- 至少覆盖以下线索：答案页标题、页底答案区、题后解析/参考答案等显式 cue。
- 若出现答案无法匹配题号，必须保留 unmatched 事实与 warning，不得伪造匹配。

## 交付物
1. 代码修改：补齐答案区识别与 `AnswerSection` 基础链路。
2. 测试补充：覆盖 detector / assembler / conversion_service 至少三层。
3. 一份样例级验证产物或摘要，写入 `artifacts/pdf2word/p1-answer-sections/`，说明哪些样例出现了 `answer_area` / `answer_section`，哪些仍未命中以及原因。
4. `result.json` 中写明：
   - 当前新增了哪些 answer cues；
   - 哪些样例被打破了 `0/5`；
   - 哪些答案内容仍需后续 teacher/review 变体再处理。

## 验收标准
1. 至少对存在明显答案线索的样例，`answer_area` 或 `answer_section` 不再全部为 0。
2. student 正文顺序、题号顺序、图片/表格主链路不回归。
3. 未匹配答案内容被保留并可解释，而不是静默丢失。
4. 相关测试通过，review/QA 可据此继续拆 teacher/review 变体。

## 下游动作
完成后进入 review-1 审查；通过后交 qa-1 验证答案区识别、答案分节产出与正文不回归。
