# 任务：实现 student/teacher/review 输出变体，打通答案解析在 Word 侧的可控呈现

## 任务类型
development

## 目标
基于现有 `AnswerSection / AnswerArea / warnings` 结构，补齐 **student / teacher / review** 三种输出变体，让答案解析在 Word 侧可控呈现：student 默认保持正文稳定，teacher/review 可显式带出答案解析与未匹配提示。

## 任务边界
- 只处理 `Exercise IR / assembler / conversion_service` 侧的输出变体，不改 detector 规则本身；答案 cue 检测由并行任务负责。
- 允许修改：`exercise_ir.py`、`exercise_docx_assembler.py`、`conversion_service.py`、相关 3 份测试，以及 `artifacts/pdf2word/p2-answer-teacher/variants/`。
- 不允许用 LLM 直接生成新的答案正文；teacher/review 只能基于已有 `AnswerSection / AnswerArea / warnings` 做呈现与编排。
- student 默认输出不能因引入变体而回归。

## 输入事实
- P2 规划要求支持 `student / teacher / review` 输出变体。
- 当前代码中 `exercise_docx_assembler.py` 已能渲染 `AnswerSection`，但缺少清晰的变体选择与稳定的 teacher/review 呈现约束。
- 当前答案检测基线主要来自 `p1-answer-sections/summary.json`，命中样例有限，因此变体实现必须对“有答案”和“无答案 / unmatched”两种情况都保持可解释。

## 约束
- `write_scope` 以 `task.json` 为准。
- `student` 必须保持默认稳定，不因 teacher/review 新能力破坏正文顺序、题号顺序和图片/表格主链路。
- `teacher / review` 只展示已有答案结构、未匹配 warning 或审校提示，不得编造答案。
- 若新增参数或 meta，优先沿用现有 service/config 路径，避免引入破坏兼容性的入口。

## 交付物
1. `student / teacher / review` 输出变体实现。
2. 对应测试更新（至少覆盖：默认 student 不回归、teacher 展示答案解析、review 保留 unmatched/warning 提示）。
3. `artifacts/pdf2word/p2-answer-teacher/variants/` 下的样例摘要或输出对比说明。
4. `result.json`：写明变体入口、teacher/review 呈现规则、student 默认不回归的验证结果。

## 验收标准
1. `student / teacher / review` 三种输出可选择且职责清晰。
2. student 默认输出不回归；teacher/review 能在有答案结构时正确呈现答案解析，在无答案结构时保留 warning/空结果解释。
3. 不生成额外幻觉答案文本。
4. 指定测试通过，且与现有 PDF→Word 主链路兼容。

## 下游动作
完成后进入 review-1 审查；通过后作为 P2 teacher/review 变体与下游 QA 抽检输入。
