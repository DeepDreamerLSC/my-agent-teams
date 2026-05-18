# Review - MinerU迁移到统一推理架构

## 结论
- 结果：`approve`
- 说明：MinerU 已接入统一推理架构，公开工厂路径可稳定返回 `DocumentOCRAdapter + MinerUNormalizer`，配置和回归测试也已补齐。

## 确认通过的点

### 1) 统一工厂路径已接通 MinerU
`backend/app/services/pdf_to_word/parser_adapters/inference_config.yaml`

`mineru` profile 已配置为：
- `adapter: document_ocr`
- `backend: mineru_cli`
- `normalizer: mineru_blocks`
- `input_mode: pdf`

这符合任务目标，不需要新增 adapter class。

### 2) `mineru_blocks` normalizer 已注册
`backend/app/services/pdf_to_word/parser_adapters/normalizers/__init__.py`

`mineru_blocks` 已进入 normalizer registry，`create_normalizer('mineru_blocks')` 可直接实例化 `MinerUNormalizer`。

### 3) `MinerUNormalizer` 的核心行为覆盖到位
`backend/app/services/pdf_to_word/parser_adapters/normalizers/mineru.py`

确认点：
- 支持 `content_list` / `middle_json` 还原到 `PageIR`
- `text / image / table / formula_candidate` 映射正确
- bbox 会按页渲染尺寸归一化
- 缺失 `confidence` 会默认 `1.0` 并进入 warnings
- JSON 解析失败会进入 warnings，不会静默吞掉

### 4) `create_adapter('mineru')` 返回真实 `DocumentOCRAdapter`
我做了干净进程复核，结果是：
- `DocumentOCRAdapter`
- `MinerUNormalizer`
- `CLIBackend`

说明 MinerU 已经进入统一推理架构的真实工厂路径，而不是只停留在测试里。

## 验证结果
- `py_compile`：通过
- `pytest tests/test_mineru_normalizer.py tests/test_pdf_to_word_inference_config.py -q`：`14 passed`
- 干净进程校验：通过

## 非阻塞观察

### 1) 测试文件改动超出当前 write_scope 记录
本轮实际修复包含 `backend/tests/test_pdf_to_word_inference_config.py`，但该文件不在 task.json 当前 write_scope 中。

这不影响代码结论，但建议后续把公共入口测试文件纳入治理记录，避免流程边界和实际修复范围不一致。
