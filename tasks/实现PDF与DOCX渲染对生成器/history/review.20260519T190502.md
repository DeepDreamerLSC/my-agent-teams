# Review - 实现PDF与DOCX渲染对生成器

## 结论
- **审查结果：request_changes**
- **recommended_next_action：pm**
- **当前是否可收口：否**

这轮实现已经完成了主干：
- source PDF / output DOCX 的页级 render pair 结构搭起来了；
- 页级 PNG、hash、页尺寸、rotation、artifact path 都有；
- `render_pair.json` 也能稳定输出 success / failed / page_count_mismatch；
- 我补跑的定向 pytest 也通过了。

但仍有一个 **P0 阻塞问题**：**默认 LibreOffice/soffice 转换超时时，失败语义没有被收敛成显式 contract。**

## 阻塞项：DOCX 默认转换超时会直接抛异常，拿不到 failed summary/artifact
### 我看到的问题
`page_renderer.py` 里的 `convert_docx_to_pdf()` 现在这样调用：
- 直接 `subprocess.run(..., timeout=timeout_seconds)`；
- 但没有捕获 `subprocess.TimeoutExpired`。

结果是：
- 如果默认 DOCX->PDF 转换超时；
- 会直接抛出原生 `TimeoutExpired`；
- `generate_render_pairs()` 也不会走到 `PageRenderError` 的失败汇总分支；
- 因而拿不到稳定的：
  - `status=failed`
  - `failure_code`
  - `errors[]`
  - `render_pair.json`

### 为什么这是 blocker
instruction 里明确要求：
- **遇到渲染失败要有显式错误语义，不能静默跳过**；
- 后续 `visual_similarity.json` 要把 render pair 当作**唯一上游证据**消费。

当前 timeout 场景下不是“语义不够漂亮”，而是**整个失败产物链断了**：
- 下游拿不到结构化失败结果；
- 只能看到一次裸异常；
- 不符合本任务要建立的 canonical render-pair contract。

### 我怎么验证到这个问题的
我补做了一个 smoke test：
- patch `shutil.which` 让代码走默认 LibreOffice 路径；
- patch `subprocess.run` 直接抛 `subprocess.TimeoutExpired`；
- 分别调用 `convert_docx_to_pdf()` 和 `generate_render_pairs()`。

结果两者都会直接抛原生 `TimeoutExpired`，不会回落成 `PageRenderError` / failed summary。

### 最小返修建议
建议按最小口径修：
1. 在 `convert_docx_to_pdf()` 里捕获 `subprocess.TimeoutExpired`；
2. 包装成显式 `PageRenderError`；
3. 最好给独立 failure code，例如：`docx_pdf_conversion_timeout`；
4. 让 `generate_render_pairs()` 在该场景下稳定输出 `failed + failure_code + errors + artifact_path`；
5. 同步补：
   - `render_pair_contract.json` failure_codes
   - `test_pdf_to_word_render_pair.py` 的 timeout 回归测试

## 我认可的部分
除这个 blocker 外，我认可这轮的主体实现：
1. `render_pdf_pages()` 已补齐页级 PNG/hash/尺寸/rotation/metadata；
2. `render_docx_pages()` 已把 DOCX->PDF->PNG 链路接上；
3. `generate_render_pairs()` 已能输出：
   - `success`
   - `failed`
   - `page_count_mismatch`
4. mismatch 场景下不会静默吞页，而是保留 `matched/source_only/docx_only`；
5. fixture contract 已把下游消费字段冻结下来；
6. `git diff --check`、`py_compile`、定向 pytest 都通过。

所以这不是推翻重做，而是**补齐一个真实运行中非常关键的失败语义缺口**。

## 非阻塞说明
- 当前任务目录没有 `verify.json`。
- 这不是本轮驳回主因；主因是 timeout 失败语义未 contract 化。

## 建议
请 dev-2 先修 timeout 失败语义这一个点，并补对应 contract/test；修完后我可以按这个点做**快速复审**。
