# 任务：补齐答案区教师版 authoritative 样例，收敛 answer_area 与 answer_section 实证

## 任务类型
development

## 目标
基于现有答案识别与 `student / teacher / review` 输出变体，实现一轮**真实样例补强**：让答案链路不再只停留在阶段性检测/QA 摘要，而是在真实 PDF→Word 产物中补出可复核的 `answer_section` / `answer_area` 证据，为后续 authoritative final archive 收口做准备。

## 任务边界
- 只处理答案区识别、题后解析归并、teacher/review 变体输出与对应样例产物。
- 不放宽 hybrid 默认发布边界，不改公式 merge 策略，不处理异步 job 产品化。
- 优先复用现有 `exercise_detector` / `exercise_docx_assembler` / `conversion_service` 主链路，不新起旁路脚本。
- 本轮产物先落到 `artifacts/pdf2word/p2-answer-teacher/`；如无需额外脚本即可自然补齐 authoritative 候选样例，可同步补充候选说明，但不要为追求“进 final-archive”而无边界扩 scope。

## 输入事实
- 当前答案专项检测、teacher/review 变体、专项 QA 报告都已完成阶段性闭环。
- 但 authoritative final DOCX 口径里，`answer_area = 0/5`、`answer_section = 0/5` 仍是明确差距。
- 现有代码与测试已经具备 `AnswerSection`、`answer_area`、teacher/review 变体基础能力，说明问题更可能出在真实样例命中率、归并规则或产物沉淀不足，而不是能力完全缺失。

## 约束
- `write_scope` 以 `task.json` 为准。
- 必须使用真实样例与真实产物，不接受只补 synthetic case 就宣称收敛。
- student 默认输出不能回归；teacher/review 新增内容不能污染 student 主正文。
- 如本轮只能稳定补出 `answer_section` 或只能补出 `answer_area`，也可以接受，但必须逐样例写清命中/未命中与 blocker。

## 交付物
1. 答案链路相关代码/测试更新。
2. `artifacts/pdf2word/p2-answer-teacher/` 下新增一轮 authoritative 候选样例产物与说明，至少包含：
   - 哪些真实样例命中了 `answer_section` / `answer_area`
   - teacher/review 产物路径
   - 未命中样例与原因
3. `result.json`：说明本轮真实命中情况、student 是否无回归、距离 authoritative final archive 还差什么。

## 验收标准
1. 至少补出一批可复核的真实样例证据，不能继续停留在 `0` 个实证样例。
2. student 默认输出无回归，teacher/review 的新增答案内容与正文边界清晰。
3. 测试通过，且真实样例结果与报告一致。
4. 对仍未命中的样例给出逐样例解释，而不是笼统描述“效果一般”。

## 下游动作
完成后进入 review-1 审查；通过后作为“答案/教师版 authoritative 证据补齐”的主输入，再决定是否进入 final-archive 常态门禁或继续拆分补样任务。
