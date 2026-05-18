# 任务：实现 Hybrid 题号顺序与阅读顺序校验器

## 任务类型
development

## 目标
补齐 Hybrid Phase 2 的题号顺序与阅读顺序校验能力：当题号归属冲突、页内阅读顺序异常或题号回退时，能在 parser_adapters 层给出明确 verdict，并作为 hybrid validator 的页级门禁输入。

## 任务边界
- 在 `order_resolver.py`、`question_region_detector.py`、`hybrid_validator.py` 内补齐顺序校验规则与门禁逻辑
- 补齐对应单测 / 集成回归
- 不修改 Qwen3-VL prompt / normalizer / review worker 路径
- 不修改 ExerciseIR / DOCX 渲染逻辑

## 输入事实
- `artifacts/pdf2word/final-archive/reports/后续技术路线.md` 已把“题号归属、阅读顺序、低置信页校验闭环”列为 Phase 2 主目标
- 当前 `QuestionRegionDetector` 已有 `reading_order_valid` 与 `resolvable/skip_enhancement` 概念，但还缺少统一的 Phase 2 顺序校验收口
- `order_resolver.py` 目前只做轻量排序和简单题号稳定化，尚未形成 Hybrid 页级质量门禁
- `artifacts/pdf2word/hybrid-e2e-validation/report.json` 显示 5 个真实样例全部 `document_fallback=true`，当前 validator 以 `bbox_out_of_bounds` 为主，但还没有单独沉淀“题号顺序/阅读顺序异常”的可观测 verdict
- `语文五年级` 是负样例，必须继续保持不可判定页跳过增强；`数学试卷`、`英语八年级` 是正样例，需要能识别可判定页与顺序异常页

## 约束
- write_scope 以 task.json 为准
- 只能在 parser_adapters / order_resolver / 对应测试范围内修改
- 不允许让 `apple_baseline` 默认主链路退化
- 不允许把顺序问题 silently auto-fix 后吞掉，必须在 report / validator 中留下可审计理由
- 负样例页仍然必须走 skip / fallback，而不是强行并回

## 交付物
1. 顺序校验实现：题号递增、页内阅读顺序、归属冲突的统一判定逻辑
2. `test_question_region_detector.py` / `test_hybrid_validator.py` / 必要的 integration test 更新
3. 能被 `hybrid-e2e-validation` 报告消费的 verdict / reason 字段（至少覆盖 wrong_order / reading_order_invalid / question_sequence_regression 等）
4. result.json：说明规则、覆盖样例、剩余风险

## 验收标准
1. 正样例页的题号/阅读顺序异常能被识别并输出明确 verdict / reason
2. `语文五年级` 继续保持不可判定页跳过增强，不发生错误并回
3. `pytest backend/tests/test_question_region_detector.py backend/tests/test_hybrid_validator.py backend/tests/test_pdf_to_word_exercise_pipeline_integration.py` 通过
4. baseline 路径无回归
5. 输出结果可被后续 review worker / QA 抽检直接引用

## 下游动作
完成后进入 review-1 审查，审查通过后由 qa-1 做回归验证，最终 PM 收口。
