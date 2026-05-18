# 任务：增强答案页与题后解析识别，推进真实样例答案区/答案分节命中率

## 任务类型
development

## 目标
在现有 `ExerciseDetector` 基础上，继续增强 **答案页、页底答案区、题后解析/解答** 的识别能力，提升真实五样例中的 `answer_section / answer_area` 命中，并把 matched / unmatched 答案事实保留下来，作为 P2 教师版专项的检测基线。

## 任务边界
- 只处理答案 cue 检测与 `AnswerSection/AnswerArea` 物化，不处理 student/teacher/review 输出变体；那是并行下游任务。
- 允许修改：`exercise_detector.py`、`test_pdf_exercise_detector.py`、`artifacts/pdf2word/p2-answer-teacher/detection/`。
- 不改 hybrid 发布边界，不改公式策略，不改 final DOCX source gate。
- 不得为了“提高命中率”伪造题号归属或静默吞掉未匹配答案。

## 输入事实
- 规划中的 P2 明确要求：识别答案页、页底答案区、题后解析，并把 `answer_area / answer_section` 从当前不可验收状态推进到可量化状态。
- 当前基线：`/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/p1-answer-sections/summary.json`
  - `current_answer_section_sample_count = 2/5`
  - `current_answer_area_sample_count = 0/5`
  - 命中样例：`数学八年级`、`数学试卷`
  - miss 样例：`五下科学`、`英语八年级`、`语文五年级`
- 当前已识别的 cue 主要是：`参考答案 / 答案与解析 / 解： / 解析：`；但页底答案区、题后解析、多页答案段落仍不稳定。

## 约束
- `write_scope` 以 `task.json` 为准。
- 必须保留 unmatched warning / miss reason，不得为了“看起来命中”而硬挂到错误题号。
- 负样例和 `document_fallback` 场景继续保守，不能给 `语文五年级` 这类样例伪造答案结构。
- 若无法提升命中率，也必须把 failure bucket、miss reason 和下一步 cue 建议写进专项产物。

## 交付物
1. `exercise_detector.py` 的答案 cue 检测增强实现。
2. 对应测试更新（至少覆盖：答案页标题、题后解析、页底答案 cue、未匹配 warning 保留）。
3. `artifacts/pdf2word/p2-answer-teacher/detection/` 下的真实五样例摘要，至少包含：
   - `answer_area_count`
   - `answer_section_count`
   - `matched/unmatched` 数量
   - 每个 miss 样例的原因
4. `result.json`：写明新增 cue、命中提升情况、剩余 miss 与后续建议。

## 验收标准
1. 当前已有的 2/5 `answer_section` 命中不得回退，并尽量提升真实样例中的答案信号覆盖。
2. `answer_area / answer_section / matched / unmatched` 可量化且逐样例可解释。
3. 未匹配答案内容被保留并标 warning，不静默丢失。
4. 指定测试通过，且不破坏 student 正文顺序与现有题号结构。

## 下游动作
完成后进入 review-1 审查；通过后作为 P2 答案识别基线，并供下游输出变体与 QA 抽检复用。
