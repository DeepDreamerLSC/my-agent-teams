# Review - 数学公式图形表格页专项视觉门禁

## 结论
- **审查结果：approve**
- **recommended_next_action：qa**
- **当前是否可直接最终收口：否**

这轮返修已经把上一轮两个阻塞点都补上了。

## 我确认通过的点
1. **focus page 缺失专项 payload 不会再静默通过**
   - `formula` focus 缺 `formula_regions`
   - `graphic` focus 缺 `graphic_regions`
   - `table` focus 缺 `table_regions`
   现在都会进入 `artifact_not_ready`，不再返回 `ready`。

2. **graphic/question_order 页面缺失 binding 证据不会再静默通过**
   - `binding_pairs=[]`
   - `binding_pair_iou` 缺失
   现在也都会进入 `artifact_not_ready`。

3. **原有专项 veto 语义没有被破坏**
   - formula audit-only 仍不能替代真实视觉分；
   - 图形-题干绑定异常、题块顺序异常、表格/公式/图形关键区域低分仍会触发 veto；
   - `downstream_visual_similarity_contract` 仍可给共性 visual_similarity / fidelity reporter 透传。

## 我补做的验证
我额外确认了：
- `py_compile`
- 定向 `pytest`
- `git diff --check`
- 上一轮 4 组最小复现

结果：
- `13 passed, 4 warnings`
- warnings 为既有 FastAPI `on_event` deprecation warnings，不阻塞结论
- 4 组最小复现现在都正确返回 `artifact_not_ready`

## 非阻塞说明
- 当前任务目录仍无 `verify.json`
- `qa_gate_state` 仍为 `pending`

所以这轮结论是：
- **review 可以 approve**
- 但**下一步应立即进入 QA**，帮助解除全学科 95 复验阻塞

## 建议
建议 **approve 并交给 qa-1**：
- 把数学专项结果并入全学科人工视觉 95 复验；
- 重点确认 reporter/QA 对 `artifact_not_ready`、`vetoes[]`、`downstream_visual_similarity_contract` 的消费与本轮 contract 一致。
