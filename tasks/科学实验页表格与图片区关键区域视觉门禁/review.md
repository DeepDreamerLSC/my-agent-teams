# Review - 科学实验页表格与图片区关键区域视觉门禁

## 结论
- **审查结果：approve**
- **recommended_next_action：qa**
- **当前是否可直接最终收口：否**

这轮返修已经把上一轮两个阻塞点都补上了。

## 我确认通过的点
1. **关键 source region 缺失时，不会再静默通过**
   - 现在 science mixed page 对 `table` / `image` / `experiment_record` / `question_stem` 建立了强 contract；
   - 缺失关键 region 时，summary/page 都会进入 `status=not_ready`，并产出 `science_required_region_missing` blocker。

2. **关键关系定义缺失时，不会再静默通过**
   - 现在对 image-question、table-question、record-table 三类必要关系建立了强 contract；
   - 即使 `adjacent_to` 被整体清空，也不会再高分通过，而是进入 `status=not_ready`，并产出 `science_required_relation_missing` blocker。

3. **原有专项 veto 语义没有被破坏**
   - 表格失真、图片区绑定断裂、实验记录区邻接异常仍能正常触发 veto；
   - `recommended_common_code` 仍可继续给公共 fidelity_veto 链路消费。

## 我补做的验证
我额外确认了：
- `py_compile`
- 定向 `pytest`
- `git diff --check`
- 上一轮 3 组最小复现

结果：
- `6 passed, 4 warnings`
- warnings 为既有 FastAPI `on_event` deprecation warnings，不阻塞结论
- 3 组最小复现现在都正确返回 `status=not_ready`

## 非阻塞说明
- 当前任务目录仍无 `verify.json`
- `qa_gate_state` 仍为 `pending`

所以这轮结论是：
- **review 可以 approve**
- 但**下一步应立即进入 QA**，帮助解除全学科 95 复验阻塞

## 建议
建议 **approve 并交给 qa-1**：
- 把科学实验页结果并入全学科人工视觉 95 复验；
- 重点确认公共 visual_similarity / fidelity_veto 链路对 `status=not_ready`、`blockers[]`、`recommended_common_code` 的消费与本轮 contract 一致。
