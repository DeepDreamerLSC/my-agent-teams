# 任务：固化 final DOCX source gate，按策略矩阵校验 source_profile 与 fallback 事实

## 任务类型
verification

## 目标
把 final DOCX 验收门禁升级为“按源感知”的常态化 gate：验收时不只看 DOCX 能否打开，而是按 P1 策略矩阵核对 `word/media`、table XML、fallback、`source_profile` 与负样例边界，避免再用单次 probe 候选量替代最终 Word 质量。

## 任务边界
- 允许修改：`model_eval_runner.py`、`test_hybrid_e2e.py`、`test_model_eval_runner.py`。
- 允许更新 `artifacts/pdf2word/final-acceptance/` 报告产物。
- 不改默认发布边界，不调整 `apple default + hybrid_experimental quality gray + formula audit-only / merge-disabled` 结论。
- 不新增新的 parser 或模型评测路线，只固化 final DOCX gate 口径。

## 输入事实
- authoritative 策略文档/JSON 已明确不同 `page_type` 的默认源、补充源、fallback 口径与 QA gate。
- 当前 final DOCX gate 已覆盖 `openable_docx / word_media / table_xml / answer_area / answer_section` 等口径，但还未把 `source_profile` 与策略矩阵绑定成显式 gate。
- `语文五年级` 这类负样例仍应保持 `baseline/document fallback only`，不能因为候选存在而误判为增强成功。

## 约束
- `write_scope` 以 `task.json` 为准。
- gate 必须把 `fallback` 解释为质量事实的一部分，而不是简单失败计数。
- 必须显式保护负样例与公式边界：`negative sample baseline-only`、`formula audit-only / merge-disabled`。
- 报告中不得使用“某模型某次候选更多”来替代 Word 最终产物质量结论。

## 交付物
1. source-profile-aware 的 final DOCX gate/summary 实现。
2. 对应测试与更新后的 `final-acceptance` 报告。
3. `result.json`：写明新增 gate 字段、如何校验负样例/fallback/source_profile，以及当前发布边界是否保持不变。

## 验收标准
1. final DOCX gate 能按策略矩阵核对 `word/media`、table XML、fallback、`source_profile`，而非只看候选数。
2. `语文五年级` 等负样例继续被正确识别为 `baseline/document fallback only`。
3. 公式仍保持 `audit-only / merge-disabled`，不被 gate 误记为缺陷性回归。
4. 指定测试通过，更新后的 `final-acceptance` 报告可直接作为后续常态化验收底稿。

## 下游动作
完成后进入 review-1 审查；通过后作为 final DOCX 常态化验收口径与后续放量评估基线。
