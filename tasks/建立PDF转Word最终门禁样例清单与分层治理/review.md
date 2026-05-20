# Review - 建立PDF转Word最终门禁样例清单与分层治理

## 结论
- **审查结果：approve**
- **recommended_next_action：pm**
- **当前是否可收口：**本任务本身可收口。

## 我核对后的结论
这轮样例治理交付是成立的，满足本任务目标：

1. **三层样例已经拆开**
   - `final_gated`
   - `variant_excluded`
   - `debug_authoritative_excluded`

2. **canonical 配对已经固定**
   - 每个样例都有唯一 `source_pdf -> output_docx`；
   - 我抽查后确认 5 个样例的 canonical 配对都唯一，且路径都存在。

3. **学科覆盖满足要求**
   - 科学：五下科学
   - 数学：数学八年级、数学试卷
   - 英语：英语八年级
   - 语文：语文五年级

4. **语文没有被错误当成“已通过正向 95”**
   - `语文五年级` 被保留在 `final_gated` 套件内；
   - 但角色明确标成 `negative_guard`，且 `eligible_for_human_visual_95=false`；
   - 这符合“语文必须纳入治理，但当前不能误宣称已达成人工视觉 95”的要求。

5. **答案区 / 教师版 / authoritative / hybrid-e2e 都已被明确排除为主线 95 证据**
   - manifest 有 `excluded_variants`；
   - 也有 `excluded_roots`；
   - README 与治理说明重复声明这些路径不能直接用于主线 95 宣称。

6. **下游可以直接消费**
   - README 和治理说明都明确：
     - render pair 生成器只读 manifest canonical 配对；
     - 人工视觉 Rubric 只按 manifest 建复核单；
     - 最终 95 重跑判定也只认 manifest。

## 审查证据
- `final-gated-manifest.json` 通过 `python3 -m json.tool`。
- `git show --check` 通过，未发现 patch 格式问题。
- 我补做了 manifest spot check，确认：
  - `sample_count=5`
  - subjects 覆盖 `chinese / english / math / science`
  - canonical source/output 配对唯一
  - 所有 `source_pdf` / `output_docx` 路径存在
  - 所有 `excluded_variants` 与 `excluded_roots` 路径存在

## 非阻塞说明
当前 manifest 明确写了：
- **暂不冻结** claim / declaration policy 类字段名；
- 当前只用 `tier` / `evaluation_role` / `eligible_for_human_visual_95` 表达治理语义。

这和《统一PDF转Word95门禁命名与对外口径》仍在返修是匹配的。我认为这属于**有意延后 schema 收敛**，不是本任务阻塞项。

## 建议
建议 **approve** 并交回 PM：
- 后续 render pair 生成器、人工视觉 Rubric、最终重跑判定直接统一消费这份 manifest；
- 等命名口径任务完成 canonical naming 返修后，再补 claim/declaration policy 字段收敛。
