# Review - 语文长文作文负样例口径重建

## 结论
- **审查结果：request_changes**
- **recommended_next_action：pm**
- **当前是否可直接收口：否**

这轮工作的方向是对的：
- 已明确“语文不能被忽略”；
- 已把当前 `语文五年级` 重新界定为 `negative_guard` / `document_fallback` / `baseline_only`；
- 已明确它**不能**作为正向人工视觉 95 证据；
- 这和全学科 Rubric、基线报告的主结论是一致的。

但机器可读 manifest 还有一个需要收敛的阻塞契约差异：**sample_key 没有与 canonical final-gated manifest 保持一致。**

## 阻塞项
### 1. `sample_key` 与 canonical manifest 不一致
我比对了：
- 当前新增文件：`chinese-samples-manifest.json`
- canonical 上游：`final-gated-manifest.json`

结果是：
- `sample_name`：一致
- `tier`：一致
- `evaluation_role`：一致
- `eligible_for_human_visual_95`：一致
- `page_type`：一致
- `source_pdf`：一致
- `output_docx`：一致
- **但 `sample_key` 不一致**：
  - 当前写的是：`chinese_grade5_current`
  - canonical 写的是：`chinese_grade5`

这不是纯文案问题，而是机器可读 contract 问题。

本任务明确要求“**要与 final-gated manifest 对齐**”。既然这份 supplemental manifest 本质上是在重建同一个语文样例的口径，就不应改写它的 canonical key；否则后续做：
- join / 对账
- 去重
- 补样前后状态迁移
- PM 汇总口径

都会多出一层不必要的 key 映射。

## 最小返修口径
建议只做最小修改：

1. 把 `samples[0].sample_key` 从 `chinese_grade5_current` 改回 **`chinese_grade5`**；
2. 如果确实需要表达“这是当前这份 supplemental policy entry”，请新增独立字段，例如：
   - `entry_id`
   - `record_role`
   - `sample_generation`
3. **不要再改 canonical sample_key。**

## 其余部分的评价
除上述问题外，其余内容我认为是成立的：
- 负样例 / fallback 不能冒充正向 95 证据，写清楚了；
- 长文 / 作文需要独立正样例，写清楚了；
- PM 可直接使用的允许说 / 不允许说，也写得比较稳；
- 文档和 manifest 的总体方向正确。

## 我补做的核对
我额外做了三类检查：
- `json.tool` 校验 manifest 语法；
- `git diff --check` 校验 patch/whitespace；
- 对照 canonical `final-gated-manifest.json`、基线报告、全学科 Rubric 做静态复核。

结论是：
- **口径方向正确**；
- **唯一阻塞项就是 canonical sample_key 不一致。**

## 建议
建议 **打回返修**，按上面的最小口径改完即可；不需要重写整份报告。返修后我可以快速复审。
