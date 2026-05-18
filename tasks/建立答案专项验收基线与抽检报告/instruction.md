# 任务：建立 P2 答案专项验收基线与抽检报告，量化 matched/unmatched 与变体稳定性

## 任务类型
verification

## 目标
在答案识别增强与 student/teacher/review 变体完成后，建立 P2 的**专项验收基线与抽检报告**：用真实五样例量化 `answer_area / answer_section / matched / unmatched`，并核对 teacher/review 变体是否稳定、不破坏 student 默认输出。

## 任务边界
- 只产出 QA/验收报告，不改业务代码。
- 允许修改：`artifacts/pdf2word/p2-answer-teacher/qa/`。
- 不重启模型横评，不调整 hybrid 发布边界，不放开公式 merge。

## 输入事实
- 规划中的 P2 验收要求：
  - 五样例中存在答案线索的样例不再停留在不可验收状态；
  - `答案题号匹配率 / 未匹配保留率 / 误归属率` 可量化；
  - teacher 版不破坏 student 版正文顺序。
- 当前 P2 将由两个前置任务提供：
  - `增强答案页与题后解析识别`
  - `实现学生版教师版审校版输出变体`

## 约束
- `write_scope` 以 `task.json` 为准。
- 必须基于真实五样例与实际产物核对，不用 synthetic case 代替最终结论。
- 报告需同时记录命中和未命中，不得只报成功样例。

## 交付物
1. `artifacts/pdf2word/p2-answer-teacher/qa/` 下的专项验收报告。
2. 报告至少包含：
   - `answer_area / answer_section / matched / unmatched` 汇总
   - teacher/review 与 student 输出差异摘要
   - 正文顺序/题号顺序是否回归
   - 每个 miss 样例的解释
3. `result.json`：给出 P2 阶段性结论和是否可继续推进后续 teacher/公式路线。

## 验收标准
1. 五样例答案专项指标可量化且逐样例可复核。
2. teacher/review 输出差异清晰，student 默认链路无回归。
3. 未命中样例与未匹配答案被如实记录。
4. 报告可直接作为 P2 阶段性收口与后续路线评估底稿。

## 下游动作
完成后进入 review-1 审查；通过后作为 P2 阶段性收口与后续 teacher/公式路线评估依据。
