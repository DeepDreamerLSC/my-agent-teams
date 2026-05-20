# 审查说明：建立95还原度最终报告器

## 结论

**审查未通过（request_changes）。当前不可收口。**

## 已确认通过项

1. 本轮交付的基础工程质量没有问题：
   - CLI 入口 `--fidelity-final-report` / `--fidelity-report-input` 已接入；
   - `fidelity_metrics.json` / `fidelity_report.md` 两份产物可正常落盘；
   - “缺项显式 missing，不假装通过” 这个方向是对的。

2. 我补充复跑了：

```bash
cd /Users/linsuchang/Desktop/work/my-agent-teams/.runtime/worktrees/chiralium/95-424f239f && \
PYTHONPYCACHEPREFIX=/private/tmp/fidelity-report-review-pyc python3 -m py_compile \
  backend/app/services/pdf_to_word/model_eval_runner.py \
  backend/tests/test_pdf_to_word_fidelity_report.py

cd /Users/linsuchang/Desktop/work/my-agent-teams/.runtime/worktrees/chiralium/95-424f239f && \
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/fidelity-report-review-pyc \
/Users/linsuchang/Desktop/work/chiralium/backend/.venv/bin/python -m pytest \
  backend/tests/test_pdf_to_word_fidelity_report.py -q \
  -o cache_dir=/private/tmp/chiralium-pytest-cache-fidelity-report-review \
  --basetemp=/private/tmp/chiralium-pytest-temp-fidelity-report-review
```

结果：`4 passed, 4 warnings`

warnings 为既有 FastAPI `on_event` deprecation warnings，不是本轮阻塞点。

## 阻塞问题

### 1. 分数/阈值语义与已冻结 95% 契约不一致，被错误压成 0-1 比例值

当前实现里：

- `_coerce_fidelity_score()` 会把任何 `>1` 的值钳制成 `1.0`
- `build_fidelity_final_report_summary()` 又直接拿它处理：
  - `threshold`
  - 各维度 `score`

也就是说，当前报告器默认假设：

- 阈值是 `0.95`
- 维度分是 `0~1`
- `overall_score = score * weight`

但上游已经冻结的共同事实源不是这个口径，而是：

- **100 分制**
- `score_threshold = 95`
- 维度 `score` 是按 points 表达的结果

上游证据：

- `backend/tests/fixtures/pdf_to_word/fidelity/fidelity_manifest.json`
  - `target.score_threshold = 95`
  - `target.score_scale = 100`
- 路线文档 `8.2 fidelity_metrics.json Schema`
  - `overall_score = 95.4`
  - 维度示例是 `19.2 / 11.0 / 17.0 / ...`

这会直接导致真实 contract 输入被误算。

我做了一个 manifest-style smoke test，用的是路线文档口径：

- `threshold = 95`
- 8 个维度分数按 points 给出

当前实现实际输出：

- `threshold = 1.0`
- `overall_score = 100.0`
- 所有大于 1 的维度分都被压成了 `1.0`

这说明报告器现在虽然能跑通自带 fixture，但**对真实 95% contract 会算错总分**。

### 2. 表格硬门禁只认 `tables`，没有绑定到真实上游维度 key

当前实现只有在维度名恰好等于：

- `tables`

时才会：

- 进入 `_normalize_fidelity_tables()`
- 计算 `has_table_xml`
- 计算 `image_fallback_table_count`
- 追加 `table_gate_failed:*`
- 生成顶层 `summary["tables"]`

但真实上游契约并不是这个 key：

- frozen manifest 用的是 `editable_word_tables`
- 路线 schema 示例用的是 `editable_table`

这意味着只要输入按真实上游 contract 命名，当前实现就会：

- 跳过表格专项 hard gate
- 顶层 `tables` 变成空对象
- `has_table_xml=false` / `image_fallback_table_count>0` 也不会被提升为真正的表格 blocker

我用 `editable_word_tables` 做了 smoke test，结果是：

- `tables = {}`
- `blocking_failures` 只剩 `overall_score_below_threshold:0.1800`
- 表格 blocker 没有触发

而本任务验收标准明确要求：

- `tables.has_table_xml` 等关键字段可断言
- “表格失败导致整体不过” 必须正确处理
- 检测到表格但没有 Word 表格 XML 不能假通过

因此这也是阻塞问题。

## 为什么现有测试没有拦住问题

当前测试和 fixture 只覆盖了**自定义的简化 contract**：

- 5 个维度
- 权重是 `0.35 / 0.2 / 0.25 / ...`
- 表格维度名固定写成 `tables`
- `overall_score` 也按 `0.9785` 这种比例值断言

所以它们只能证明：

> “当前这套 0-1 风格 fixture 可以跑通”

但不能证明：

> “它与 frozen manifest / 95% 路线文档的真实 contract 一致”

## 建议返修方向

1. **先统一分数 contract**
   - 与 frozen manifest / 路线文档对齐到 100 分制；或
   - 明确新增 raw rate -> weighted points 的转换层；
   - 但不能继续把 `95` / `19.2` / `17.0` 直接 clamp 到 `1.0`。

2. **统一表格维度 key**
   - 选择真实 canonical key；或
   - 在 reporter 内显式做映射：
     - `editable_word_tables`
     - `editable_table`
     - -> 输出 `tables`

3. **补真实 contract 测试**
   - 至少补一条 100 分制 fixture：
     - `threshold = 95`
     - `overall_score = 95.4`
   - 至少补一条 manifest-style 表格 fixture：
     - 使用 `editable_word_tables` 或最终 canonical key
     - 断言 `tables.has_table_xml`
     - 断言 `table_gate_failed:*`

## 总结

这次交付已经把“报告器壳子”和“示例 fixture”搭出来了，但**目前接的是一套自定义 0-1 简化契约，不是上游已经冻结的 95% fidelity 正式契约**。在分数语义和表格维度 contract 修正之前，我不能 approve，也不建议把它当作 quality/hybrid_async 是否达到 95% 的统一出口。
