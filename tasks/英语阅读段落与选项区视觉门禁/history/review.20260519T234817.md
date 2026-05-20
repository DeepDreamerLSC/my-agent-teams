# 审查结论：request_changes

本轮**不通过**。现有 english 专项评分、critical fallback 页 veto、fixture 与 pytest 覆盖主方向是对的，但顶层 contract 还有一个阻塞缺口，当前不能放行。

## 我确认已经做对的部分

1. **专项评分已落地**
   - `reading_passage`、`options`、`stem_option_distance` 都能产出独立分数
   - happy fixture 本地 smoke 为 `ready / 0.9773`

2. **版面线性化不会误判为高还原**
   - `english_reading_linearized_fail.json` 会打出：
     - `english_reading_paragraph_layout_broken`
     - `english_option_indentation_broken`
     - `english_stem_option_spacing_broken`

3. **critical fallback 页 veto 已生效**
   - `english_reading_fallback_fail.json` 会稳定触发 `english_critical_fallback_page_layout_broken`

4. **页内 contract 缺失已覆盖**
   - 缺 `required region`
   - 缺 `required layout signal`
   - 缺 `required relation`
   都会进入 `not_ready`

5. **现有 pytest 可通过**
   - 本地复跑：`7 passed, 4 warnings`

## 阻塞问题

### 1) 顶层 `pages` 缺失/为空时，会被错误标成 `ready`
我本地直接复现：

- `evaluate_english_visual_gate({})`
- `evaluate_english_visual_gate({'pages': []})`

当前两者都会返回：
- `status = ready`
- `overall_score = 0.0`
- `human_review_required = false`
- `blockers = []`
- `pages = []`

这会导致**没有任何英语专项页数据**的 payload，被误当成“可消费成功结果”。

从实现看，问题来自：
- `english_visual_gate.py` 顶层把非 list 的 `pages` 直接归一化成 `[]`
- 最终 `status` 只看 page-level blockers
- 空 `pages` 不会产生任何 blocker，于是错误返回 `ready`

这与任务目标“英语阅读/选项区可产生专项分数或失败原因、结果可被最终 reporter 消费”不一致；空结果至少应被标成**顶层 contract not_ready**，而不是静默成功。

## 最小返修口径

请按最小范围修这两点：

1. **补顶层 pages contract blocker**
   - `pages` 缺失时：返回 `not_ready`
   - `pages=[]` 时：返回 `not_ready`
   - 给出明确 blocker code / summary（命名可由 dev 定，但语义必须稳定）

2. **补回归测试**
   - `payload` 缺失 `pages`
   - `pages=[]`
   - 断言两种场景都不会再返回 `ready + human_review_required=false + blockers=[]`

如果下游 reporter 已开始消费该产物，还需要顺手确认：**空英语专项结果不会被 consumer 当成 ready 成功结果**。

## 非阻塞提醒

- 当前任务目录没有顶层 `verify.json`
- 建议返修回提或进入 QA 门禁时补正式 verify 留痕

## 建议下一步

- `recommended_next_action = dev`
