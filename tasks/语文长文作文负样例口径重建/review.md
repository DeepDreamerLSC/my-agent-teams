# Review - 语文长文作文负样例口径重建

## 结论
- **审查结果：approve**
- **recommended_next_action：pm**
- **当前是否可直接收口：是（按本任务 review_pass_only 口径）**

这轮返修已经把上一轮唯一阻塞项修掉了。

## 我确认通过的点
### 1. canonical `sample_key` 已对齐回上游真值
上一轮的问题是：
- supplemental manifest 里写成了 `chinese_grade5_current`
- 但 canonical `final-gated-manifest.json` 里是 `chinese_grade5`

现在已经修正为：
- `samples[0].sample_key = chinese_grade5`

我重新对账后确认，以下字段都与 canonical 语文行一致：
- `sample_key`
- `sample_name`
- `tier`
- `evaluation_role`
- `eligible_for_human_visual_95`
- `page_type`
- `source_pdf`
- `output_docx`

所以之前那条 machine-readable contract mismatch 已经消失。

### 2. supplemental/current policy 语义也保住了
这轮没有为了对齐主键而丢失“当前这份 supplemental policy entry”的语义，而是改成了新增字段承载：
- `entry_id=chinese_grade5_current_policy`
- `record_role=supplemental_policy_entry`
- `sample_generation=current_negative_document_fallback_baseline`

这个做法是对的：
- canonical sample_key 保持稳定；
- supplemental 说明放到附加字段里；
- 下游 join / 去重 / 对账不会再被主键漂移干扰。

### 3. 语文本身的口径仍然正确
返修后，原本正确的主结论没有被破坏：
- 语文不能被忽略；
- 当前 `语文五年级` 仍然是 `negative_guard` / `document_fallback` / `baseline_only`；
- 不能作为正向人工视觉 95 证据；
- 若 PM 想把语文纳入全学科人工视觉 95 宣称，仍需补充语文长文/作文正样例并完成 render pair + visual_similarity + Rubric 复验。

这部分和全学科 Rubric、基线报告仍然一致。

## 我补做的核对
我额外确认了：
- `json.tool`：manifest JSON 合法；
- canonical 对账：关键字段全部一致；
- grep：旧错误主键 `chinese_grade5_current` 不再作为 canonical sample_key 残留；
- `git diff --check`：无 patch / whitespace 问题。

## 建议
建议 **approve** 并交回 PM。

按当前任务配置：
- `qa_gate_state = skipped`
- `auto_close_policy = review_pass_only`

因此这轮 review 通过后，PM 可以按该任务既定口径推进收口；后续是否把语文纳入本轮人工视觉 95 宣称，仍由 PM 基于文档结论决定。
