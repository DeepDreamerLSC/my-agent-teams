# 任务：搭建 PDF 转 Word 本地模型横评框架

## 任务类型
development

## 目标
在 `backend/app/services/pdf_to_word/` 下搭建 `model_eval_runner.py` 评估框架和 `parser_adapters/` 适配器目录，使得各候选模型（MinerU、GLM-OCR、PaddleOCR-VL、Qwen3-VL、GLM-4.6V-Flash）可以统一跑批并输出标准化对比结果。本次只实现框架骨架和 `apple_baseline` 适配器，其他模型适配器后续任务补齐。

## 任务边界
- 只搭建框架代码，不安装任何新模型依赖
- 只实现 `apple_baseline` 适配器（封装当前 Apple Worker CLI 调用）
- 其他模型适配器（mineru、glm_ocr、paddleocr_vl 等）留空接口，后续任务逐步补齐
- 不修改现有 `conversion_service.py`、`parser_client.py` 等生产链路代码

## 输入事实
- 参考方案：`/Users/linsuchang/Desktop/work/chiralium/design/pdf2word/PDF习题转Word详细技术方案.md` Section 20.3
- 样例 PDF 目录：`/Users/linsuchang/Desktop/work/chiralium/example/扫描件 `（注意目录名末尾有空格）
- 当前 Apple Worker：`/Users/linsuchang/Desktop/work/chiralium/workers/apple_pdf_worker/worker.py`
- 当前 parser 链路：`conversion_service.py` -> `parser_client.py` -> Apple Worker CLI
- 当前 block 模型：`backend/app/services/pdf_to_word/models.py` 中的 `PDFSourceBlock`

## 约束
- write_scope 以 task.json 为准
- 不修改生产链路代码
- 框架必须支持后续通过 `--profile <name>` 指定只跑某一个候选模型
- 所有候选模型的输出必须统一为 PageIR / PDFSourceBlock 兼容结构

## 交付物

### 1. `parser_adapters/base_adapter.py` — 基础适配器接口

```python
class BaseParserAdapter(ABC):
    """所有候选模型适配器的基类"""
    profile_name: str  # e.g. "apple_baseline", "mineru", "glm_ocr"

    @abstractmethod
    def parse(self, pdf_path: str, pages: list[int] | None = None, dpi: int = 200) -> AdapterResult:
        """解析 PDF，返回标准化结果"""
        ...

    @abstractmethod
    def is_available(self) -> bool:
        """检查该适配器依赖是否已安装"""
        ...

@dataclass
class AdapterResult:
    profile: str
    sample_name: str
    pages: list[PageIR]          # 每页的 block 列表
    metrics: EvalMetrics         # 耗时、内存等
    warnings: list[str]
    error: str | None = None

@dataclass
class PageIR:
    page_index: int
    width: float
    height: float
    blocks: list[PDFSourceBlock]  # 复用现有 block 模型

@dataclass
class EvalMetrics:
    total_seconds: float
    per_page_seconds: list[float]
    peak_memory_mb: float
    model_load_seconds: float | None
    page_count: int
    block_count: int
    image_candidate_count: int
    formula_candidate_count: int
```

### 2. `parser_adapters/apple_baseline_adapter.py` — Apple 基线适配器

封装当前 Apple Worker CLI 调用逻辑（参考 `parser_client.py` 中 `parse_with_backend` 的 apple 分支），将 worker 输出转换为 `AdapterResult`。

### 3. `parser_adapters/__init__.py` — 适配器注册表

```python
ADAPTER_REGISTRY: dict[str, type[BaseParserAdapter]] = {
    "apple_baseline": AppleBaselineAdapter,
    # 后续注册: "mineru": MinerUAdapter, ...
}
```

### 4. `model_eval_runner.py` — 评估主入口

CLI 入口，支持：
```bash
python -m app.services.pdf_to_word.model_eval_runner \
  --samples-dir "/path/to/扫描件 " \
  --output-dir "artifacts/pdf2word/model-eval" \
  --profiles apple_baseline \
  [--pages 0,1,2]  # 可选，只跑指定页
```

对每个样例 × 每个 profile 运行适配器，输出统一目录结构：
```
<output-dir>/<timestamp>/
  <profile>/<sample_name>/
    pages.jsonl          # 每页 PageIR JSON
    metrics.json         # EvalMetrics
    warnings.json        # 警告列表
    output.docx          # 走现有 DOCX assembler 生成
```

### 5. `tests/test_model_eval_runner.py` — 测试

- 测试 `BaseParserAdapter` 接口规范
- 测试 `ADAPTER_REGISTRY` 注册和查找
- 测试 `apple_baseline` 适配器的 `is_available()` 在有/无 worker 环境下返回正确值
- 测试 `model_eval_runner` 的 CLI 参数解析
- 测试输出目录结构生成逻辑（用 mock 适配器）

## 验收标准
1. `parser_adapters/base_adapter.py` 定义了 `BaseParserAdapter`、`AdapterResult`、`PageIR`、`EvalMetrics`
2. `apple_baseline_adapter.py` 能调用 Apple Worker CLI 并将输出转为 `AdapterResult`
3. `model_eval_runner.py` 支持 `--profiles`、`--samples-dir`、`--output-dir`、`--pages` 参数
4. 所有测试通过：`cd backend && python -m pytest tests/test_model_eval_runner.py -v`
5. 不修改任何现有生产链路文件
6. 代码风格与项目现有 `services/pdf_to_word/` 模块一致

## 下游动作
完成后进入 review（review-1），通过后可用于实际跑批 apple_baseline 样例。后续任务将逐步补齐 mineru、glm_ocr、paddleocr_vl 等适配器。
