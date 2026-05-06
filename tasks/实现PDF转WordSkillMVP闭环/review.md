# 审查意见：实现 PDF 转 Word Skill MVP 闭环

**审查者**：review-1
**审查时间**：2026-05-06
**任务状态**：ready_for_merge
**审查结论**：**通过**

---

## 一、修改范围 vs write_scope

| 检查项 | 结果 |
|--------|------|
| result.json 列出 14 个文件 | 全部在 task.json.write_scope 内 |
| 未修改 chat.py / file_service.py / 通用 skill 链路 | 符合任务约束 |
| git diff 中出现的其他文件（chat.py、schemas 等） | 属于其他任务变更，非本任务修改 |
| 未引入第三方依赖 | 使用已有 `office_export_service.build_docx_bytes` 生成 OOXML zip |

**结论：修改范围合规，无越界。**

## 二、验收标准逐条检查

### 1. manifest 合规性
- `runtime_backend=subprocess` ✓
- `allowed_extensions=[".pdf"]` ✓
- `max_files=1` ✓
- `timeout_sec=900` ✓
- `supports_file_parse=true` ✓
- `output_format=docx` ✓

### 2. skill.py 职责边界
- 只做输入校验、模式解析、调用 PDFConversionService、返回 `display_type=file` ✓
- PDF 从 `context.uploaded_files[0].stored_path` 取 ✓
- 无文件 / 多文件 / 非 PDF / 文件不存在 / stored_path 缺失均有可读错误 ✓

### 3. PDFConversionService mock/fixture 闭环
- 使用 fixture 构造 PDFConversionDocument（含段落、表格降级文本、图片占位、说明） ✓
- 输出包含 warnings 与转换说明 ✓
- `to_meta()` 显式标注 `mock_backend: "fixture"`，避免误导 ✓

### 4. file payload 结构
- 包含 `file_name`、`file_path`、`file_size`、`mime_type` ✓
- DOCX 为合法 zip（测试验证 `word/document.xml` 存在） ✓

### 5. 错误边界
- 无文件 → 可读错误 ✓
- 多文件 → 可读错误 ✓
- 非 PDF → 可读错误 ✓
- 文件不存在 → 可读错误 ✓
- 非 mock 模式 → RuntimeError 提示开启 mock ✓
- assemble 失败 → 不写出半成品文件（monkeypatch 测试覆盖） ✓

### 6. 测试覆盖
- `test_pdf_to_word_skill.py`：5 个测试（manifest 声明、SkillManager 发现、完整执行返回 DOCX、subprocess 通路、输入校验 4 种异常、文件不存在） ✓
- `test_pdf_to_word_service.py`：4 个测试（DOCX 有效性 + meta、缺失/非法 PDF、assembly 失败不写半成品） ✓
- 35 个现有 skill 测试回归通过 ✓

## 三、代码质量评价

### 优点
1. **分层清晰**：skill → service → assembler → workspace 职责分明，后续替换 mock 为真实 MinerU 只需改 `conversion_service.py` 的 `_build_mock_document`
2. **输入校验严格**：PDF header 校验（`%PDF-`）、后缀校验、存在性校验三层防护
3. **workspace 生命周期管理**：context manager 保证临时目录清理
4. **透明的 mock 标记**：meta、warnings、转换说明均明确标注 MVP/mock/fixture 性质，不伪造高保真结果
5. **配置集成干净**：三个 `PDF_TO_WORD_*` 环境变量合理集成到 pydantic Settings，有 path validator 保护
6. **mode 解析完善**：支持中英文关键词（快速/极速/高质量/高保真），参数和 query 双入口

### 改进建议（非阻塞，后续迭代可处理）
1. **测试辅助函数重复**：`_write_pdf` 在两个测试文件中重复定义，可提取到 `conftest.py`
2. **workspace 临时文件清理时机**：当前 workspace 在 `__exit__` 清理，若进程崩溃可能残留；可考虑 atexit 注册兜底（非 MVP 必须）

## 四、风险评估

| 风险项 | 严重程度 | 说明 |
|--------|---------|------|
| mock_enabled=True 硬编码为默认值 | 低 | 已在 result.json 标注；接入真实 MinerU 时切换即可 |
| page_count 正则估算 | 低 | `/Type /Page\b` 精度有限但对 MVP 足够，不影响转换质量 |
| OOXML 格式能力有限 | 低 | 无 python-docx 依赖是设计选择，满足 MVP 验收 |

**以上风险均为已知且可接受，不阻塞合并。**

## 五、结论

**通过。** 实现严格遵循任务边界，修改范围与 write_scope 一致，分层设计为后续 MinerU sidecar 接入留出清晰替换点。9 个新测试覆盖正常路径和异常边界，35 个现有测试无回归。建议 PM 推进至 QA 或直接进入下一阶段 MinerU sidecar Adapter 接入。
