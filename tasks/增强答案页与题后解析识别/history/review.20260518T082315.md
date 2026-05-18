**结论**
`request_changes`

本轮增强方向基本对路，答案页标题、题后解析 heading、视觉作答区物化和五样例 replay 都补上了；但当前实现引入了一个阻塞回归：进入 `answer_section` 后，后续 `table/image` 会被优先吸进当前答案项，而不是先按 `assigned_question_id / assigned_region_id` 路由回真正所属题目。

**阻塞问题**
[`exercise_detector.py`](/Users/linsuchang/Desktop/work/chiralium/backend/app/services/pdf_to_word/exercise_detector.py:65) 在循环开头新增了视觉块捷径分支。这个分支发生在 `_attach_visual_block()` 之前，所以当文档出现“题后答案 cue 之后又开始新题，新题带表格/图片”时，已分配给新题的视觉块仍会被挂到上一题答案解析里。

最小复现场景：
- `1. 第一题`
- `答案：步骤一`
- `2. 第二题`
- `table(meta.assigned_question_id='2', assigned_region_id='p1:q2:1')`

当前实际输出里，这个表格会进入前一题的 `answer_sections[0].items[0].blocks`，而不是第 2 题本体。这个行为已经违反任务约束里“不得为了提高命中率伪造题号归属”。

**对产物的影响**
[`summary.json`](/Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/p2-answer-teacher/detection/summary.json:6) 里的 `matched_answer_item_count = 3`、`unmatched_answer_item_count = 0` 和若干样例 `hit` 结论，当前只能说明命中了部分答案 cue，不能证明题号归属正确。修掉上述路由问题之后，应重新 replay 五样例，再刷新 aggregate/sample 统计。

**验证证据**
- 定向测试已跑：`tests/test_pdf_exercise_detector.py`，结果 `6 passed, 4 warnings`
- 额外最小复现已验证出错题号归属
- 现有测试缺少“答案 cue 后重新进入新题 + assigned visual block”的回归用例

**非阻塞补充**
[`result.json`](/Users/linsuchang/Desktop/work/my-agent-teams/tasks/增强答案页与题后解析识别/result.json:1) 过于简略，没有按 instruction 写出新增 cue、命中提升、剩余 miss 和建议，补修时一并补齐会更稳。
