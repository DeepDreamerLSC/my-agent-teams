# 任务：MinerU 迁移到统一推理架构

## 任务类型
development

## 目标
将 MinerU 从独立脚本/mineru_client 路径迁移到统一推理框架的 DocumentOCRAdapter + normalizer 模式，使其可通过 `create_adapter('mineru')` / `model_eval_runner --profiles mineru` 使用。

## 任务边界
- 只新增 normalizer 和更新配置，不修改 DocumentOCRAdapter 核心逻辑
- 不修改 mineru_client.py（保留现有生产链路）
- 不做样例跑批（跑批是单独任务）

## 输入事实
- 统一推理框架已完成（Phase A-D）
- 现有 MinerU 实现：`backend/app/services/pdf_to_word/mineru_client.py`
  - CLI 调用 magic-pdf，解析 content_list.json / middle.json
  - block 映射：text / image / table / formula_candidate
- 统一框架入口：`parser_adapters/inference/registry.py` 的 `create_adapter()`
- DocumentOCRAdapter：`parser_adapters/document_ocr_adapter.py`
- Backend：`inference/cli_backend.py`（CLI 类型）
- 参考 normalizer：`parser_adapters/normalizers/glm_ocr.py`
- 现有对比数据：MinerU 在 0/5 样例上优于 baseline（可能因 lite 模式、OCR 配置等）

## 约束
- write_scope 以 task.json 为准
- Normalizer 必须实现 `ParserOutputNormalizer` Protocol（name, to_page_ir）
- 不新增 adapter class，复用 DocumentOCRAdapter
- 不修改生产链路（mineru_client.py 保持不变）

## 交付物

### 1. `normalizers/mineru.py`
- 实现 `MinerUNormalizer(ParserOutputNormalizer)`
- `name = "mineru_blocks"`
- `to_page_ir()`: 将 MinerU CLI 输出（content_list.json 格式）转为 PageIR / PDFSourceBlock
- block kind 映射：参考 mineru_client.py 的现有映射逻辑
- bbox 坐标归一化为 PDF points
- confidence 缺失时默认 1.0 并加 warning
- JSON 解析失败进入 warnings

### 2. 更新 `inference_config.yaml`
- 确认 `mineru` profile 配置正确：
  - adapter: document_ocr
  - backend: 指向 MinerU CLI backend
  - normalizer: mineru_blocks
  - input_mode: pdf

### 3. 测试 `test_mineru_normalizer.py`
- mock MinerU 输出 → 正确 PageIR / PDFSourceBlock
- 各种 block kind 映射正确
- 缺失 bbox / confidence 的处理
- JSON 解析失败 → warnings
- `create_adapter('mineru')` 返回真实 DocumentOCRAdapter + MinerUNormalizer

## 验收标准
1. `MinerUNormalizer` 实现 `ParserOutputNormalizer` Protocol
2. `create_adapter('mineru')` 返回真实 DocumentOCRAdapter 配置了 MinerUNormalizer
3. `normalizers/__init__.py` 注册了 `mineru_blocks`
4. 不新增 adapter class，不修改 mineru_client.py
5. 所有测试通过：`cd backend && python -m pytest tests/test_mineru_normalizer.py -v`

## 下游动作
完成后 MinerU 可通过统一框架跑批，并可调整配置（full 模式、不同 OCR 引擎）后重新对比 apple_baseline。
