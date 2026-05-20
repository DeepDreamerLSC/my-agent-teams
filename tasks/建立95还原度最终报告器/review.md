# 审查说明：建立95还原度最终报告器

## 结论

**审查通过（approve）。当前可收口。**

## 本轮重点复核点

按 PM 同步，我本轮重点只复核两件事：

1. **100 分制 contract 是否修正完成**
2. **`editable_word_tables` / `editable_table` 到 `tables` 的映射与表格硬门禁是否修正完成**

结论：这两点都已修好。

## 通过依据

### 1. 100 分制 contract 已对齐 frozen 95% 契约

当前实现已不再把 `threshold` 和各维度 `score` 当成 `0~1` 比例值处理：

- `FIDELITY_FINAL_REPORT_DEFAULT_THRESHOLD` 已改为 `95.0`
- `_coerce_fidelity_score()` 不再把 `>1` 的值 clamp 到 `1.0`
- 维度分和总分都按 points 口径累计

我补做的 100 分制 smoke test 结果：

- 输入：`threshold=95`，维度分使用路线文档风格的 points 值
- 输出：`threshold=95.0`
- 输出：`overall_score=93.4`

说明之前那种 `threshold=1.0 / overall_score=100.0` 的 contract 错位已经消失。

### 2. 表格别名已统一归一到 `tables`

当前实现已新增：

- `FIDELITY_TABLE_DIMENSION_ALIASES = ('editable_table', 'editable_word_tables', 'tables')`
- weight payload / dimension payload 都会先做别名归一

所以现在：

- frozen manifest 风格的 `editable_word_tables`
- 路线 schema 风格的 `editable_table`

都会统一进入最终输出里的：

- `summary["tables"]`

这和上一轮 review 要求一致。

### 3. 表格硬门禁在真实别名输入下能稳定触发

我补做了表格 alias + blocker smoke test：

- 输入使用 `editable_word_tables`
- `table_xml_present=false`
- `image_fallback_table_count=2`

输出结果正确为：

- `tables.has_table_xml = false`
- `tables.status = fail`
- `blocking_failures` 包含：
  - `table_gate_failed:detected_without_word_table_xml`
  - `table_gate_failed:image_fallback_present`

说明“检测到表格但没有 Word 表格 XML 必须失败”的硬门禁现在已经绑定到真实 contract key，而不是只对 synthetic `tables` key 生效。

## 补充验证

我额外复跑了：

```bash
cd /Users/linsuchang/Desktop/work/my-agent-teams/.runtime/worktrees/chiralium/95-424f239f && \
PYTHONPYCACHEPREFIX=/private/tmp/fidelity-report-rereview-pyc python3 -m py_compile \
  backend/app/services/pdf_to_word/model_eval_runner.py \
  backend/tests/test_pdf_to_word_fidelity_report.py
```

以及：

```bash
cd /Users/linsuchang/Desktop/work/my-agent-teams/.runtime/worktrees/chiralium/95-424f239f && \
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/fidelity-report-rereview-pyc \
/Users/linsuchang/Desktop/work/chiralium/backend/.venv/bin/python -m pytest \
  backend/tests/test_pdf_to_word_fidelity_report.py -q \
  -o cache_dir=/private/tmp/chiralium-pytest-cache-fidelity-report-rereview \
  --basetemp=/private/tmp/chiralium-pytest-temp-fidelity-report-rereview
```

结果：`4 passed, 4 warnings`

warnings 为既有 FastAPI `on_event` deprecation warnings，不构成阻塞。

## 非阻塞备注

- 本轮任务目录仍无 `verify.json`。不过当前 `result.json`、补充复跑测试和 smoke 复核已经足以支撑 review 通过。

## 总结

上一轮 review 提出的两项阻塞问题已经被正面修复：

- **100 分制 contract 已对齐**
- **表格 alias 映射与硬门禁已对齐**

因此这次我给出 **approve**，可以进入 PM 收口 / 后续集成流程。
