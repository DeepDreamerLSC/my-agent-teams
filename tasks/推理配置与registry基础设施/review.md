# 审查说明：推理配置与registry基础设施

## 结论

**驳回并请求补修（request_changes）**。

本次实现的 YAML 配置、`InferenceConfig` 解析、`--list-profiles` / `--dry-run` CLI 入口基本齐全，Section 7.1 要求的 7 个 backends 和 6 个 profiles 也都已写入；`create_adapter("apple_baseline", config=...)` 仍能创建 `AppleBaselineAdapter`，显式指定 `--profiles apple_baseline` 的路径没有被破坏。

阻塞问题在于：**默认 profile 选择策略和当前 enabled 配置不匹配**。现在不传 `--profiles` 时，runner 会把尚未实现或当前不可用的 profiles 一起纳入默认执行集，但执行前并不会检查 `is_available()`。这使得 Phase A 暴露出一个“默认就可能立刻失败”的运行路径，不适合作为基础设施阶段的合并结果。

## 审查范围

- `tasks/推理配置与registry基础设施/instruction.md`
- `tasks/推理配置与registry基础设施/result.json`
- `backend/app/services/pdf_to_word/parser_adapters/inference_config.yaml`
- `backend/app/services/pdf_to_word/parser_adapters/inference/config.py`
- `backend/app/services/pdf_to_word/parser_adapters/inference/registry.py`
- `backend/app/services/pdf_to_word/parser_adapters/__init__.py`
- `backend/app/services/pdf_to_word/model_eval_runner.py`
- `backend/tests/test_pdf_to_word_inference_config.py`
- `backend/tests/test_model_eval_runner.py`
- 对照设计：`design/pdf2word/PDF转Word本地模型横评推理架构落地方案.md` Section 7.1 / 10 / 13

## 复核结果

### 已满足部分

- `inference_config.yaml` 与设计文档 Section 7.1 基本一致，7 个 backend、6 个 profile 均已覆盖。
- `InferenceConfig.load()` 能正确加载 YAML，并支持 `PDF_TO_WORD_INFERENCE_CONFIG` 覆盖配置文件路径。
- `--list-profiles`、`--dry-run`、`--no-docx` 已接入，相关单测通过。
- `create_adapter("apple_baseline", config=...)` 仍返回 `AppleBaselineAdapter`，baseline 显式 profile 路径未被破坏。

### 阻塞问题

- `resolve_requested_profiles()` 在未显式传 `--profiles` 时，会直接返回所有 enabled profiles。
- 但当前 YAML 把 `paddleocr_vl`、`qwen3_vl_8b`、`qwen3_vl_32b`、`glm_46v_flash` 全部标成 `enabled: true`；这些 profile 在 Phase A 仍是占位 adapter，`is_available()` 固定返回 `False`。
- `run_evaluation()` 又不会先做可用性筛选，而是直接 `adapter.parse()`。

我复核了默认 profile 集与 adapter 可用性，结果是：

- `apple_baseline`：available
- `glm_ocr`：当前环境 unavailable
- `paddleocr_vl`：unavailable（占位）
- `qwen3_vl_8b`：unavailable（占位）
- `qwen3_vl_32b`：unavailable（占位）
- `glm_46v_flash`：unavailable（占位）

这意味着**不传 `--profiles` 的 runner 默认执行路径并不安全**。至少在 Phase A，不应该把未落地/不可运行的 profile 作为默认执行集。

## 测试复核

已复跑：

```bash
cd /Users/linsuchang/Desktop/work/chiralium/backend
PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/chiralium-pyc   .venv/bin/python -m py_compile   app/services/pdf_to_word/parser_adapters/inference/config.py   app/services/pdf_to_word/parser_adapters/inference/registry.py   app/services/pdf_to_word/parser_adapters/__init__.py   app/services/pdf_to_word/model_eval_runner.py   tests/test_pdf_to_word_inference_config.py

TMPDIR=/private/tmp PYTHONDONTWRITEBYTECODE=1 PYTHONPYCACHEPREFIX=/private/tmp/chiralium-pyc PYTEST_ADDOPTS='-p no:cacheprovider'   .venv/bin/python -m pytest   tests/test_pdf_to_word_inference_config.py   tests/test_model_eval_runner.py -q
```

结果：`15 passed, 4 warnings`。

warnings 为现有 FastAPI `on_event` 弃用提示，不阻塞本次结论。

## 非阻塞意见

1. `apple_baseline` 当前仍是兼容性特例：`create_adapter()` 会直接返回 `AppleBaselineAdapter(**kwargs)`，并不会真正消费 YAML 中的 `apple_cli` backend 配置。行为保持住了，但“完全统一到 profile/backend 抽象”这件事还没有在 baseline 上成立。建议后续明确把这点记录为 Phase A 例外，或在后续阶段补齐配置注入。

## 建议修改

优先建议两种修法任选其一：

1. **把未落地或默认不可运行的 profile 改成 `enabled: false`**，至少保证默认执行集只包含当前可运行的 profile；
2. **保留 enabled 配置，但 runner 默认执行前先基于 `is_available()` 过滤或 fail-fast**，并给出明确错误信息，而不是直接在 `parse()` 阶段撞到占位实现。

同时补一条回归测试，覆盖“未传 `--profiles` 时默认执行集”的行为。

## 下一步

建议退回 PM 派发补修，不建议直接进入 QA。

审查时间：2026-05-14T17:03:41+08:00
