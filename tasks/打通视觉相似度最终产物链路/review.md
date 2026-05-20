# review-1 审查结论

- 结论：`approve`
- 是否已解除“缺少 canonical visual_similarity.json 导致最终 95% 判定天然卡死”的主阻塞：**是**
- 推荐下一步：`qa`

## 本轮重点复核
按任务目标，我重点核对了三件事：

1. canonical artifact 名称是否统一为 `visual_similarity.json`
2. `model_eval_runner` / visual gate / fidelity final report 的消费链路是否真正接通
3. contract-only / stub 场景是否会被显式识别，而不是伪造通过

## 审查结果

### 1. canonical artifact 与 CLI 入口已接通
- `backend/app/services/pdf_to_word/model_eval_runner.py`
  - 新增 `--visual-similarity-artifact`
  - 新增 `--visual-similarity-input`
  - 新增 `--visual-similarity-mode`
  - 新增 `--visual-similarity-parser-backend`
  - 新增 `--fidelity-final-report`
  - 新增 `--fidelity-report-input`
- `write_visual_similarity_artifacts()` 只写 canonical `visual_similarity.json`，没有把 `visual_similarity_report.json` 当 required artifact 落盘。

### 2. visual similarity gate contract 与 95 分制口径一致
- `backend/app/services/pdf_to_word/visual_similarity_gate.py`
  - 冻结 `visual_similarity` 维度 key / weight=17
  - 明确保留 `quality/hybrid_async` 边界
  - default sync 不触发 render diff / slow model
  - active slow-model candidate 仍只有 `qwen3_vl_8b`
  - `glm_46v_flash` 仍在 blocked/comparison-only

### 3. fidelity final report 已能优先消费 canonical artifact
- `build_fidelity_final_report_summary()` 现在会读取 `visual_similarity_artifact_path`
- 当 artifact 缺失时，不再只是历史上的“天然没文件”；
- 当 artifact 是 contract-only / stub 时，会显式报：
  - `visual_similarity_artifact_not_ready:contract_only_no_renderer_or_slow_model_invoked`
- 当 artifact 是 `quality_hybrid_async_artifact_ready` 时，visual similarity 17 分会真实并入最终总分。

### 4. 测试与 fixture 覆盖了生成 + 消费两侧
- `backend/tests/test_pdf_to_word_visual_similarity_gate.py`
  - 覆盖 contract shape、default sync 边界、quality/hybrid_async scoring、slow-model candidate、missing render pair 等
- `backend/tests/test_pdf_to_word_fidelity_report.py`
  - 覆盖 pass / table blocker / missing dimension / canonical artifact consumed / contract-only artifact not false-pass
- `backend/tests/test_model_eval_runner.py`
  - 覆盖 CLI 参数解析与 canonical filename 落盘

## Reviewer 本地补充验证
我补充复跑通过：

```bash
PYTHONPYCACHEPREFIX=/private/tmp/chiralium-pycache-visual-review \
PYTHONDONTWRITEBYTECODE=1 \
/Users/linsuchang/Desktop/work/chiralium/backend/.venv/bin/python -m py_compile \
  backend/app/services/pdf_to_word/model_eval_runner.py \
  backend/app/services/pdf_to_word/visual_similarity_gate.py \
  backend/tests/test_model_eval_runner.py \
  backend/tests/test_pdf_to_word_visual_similarity_gate.py \
  backend/tests/test_pdf_to_word_fidelity_report.py

PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=backend \
/Users/linsuchang/Desktop/work/chiralium/backend/.venv/bin/python -m pytest -p no:cacheprovider \
  backend/tests/test_pdf_to_word_visual_similarity_gate.py \
  backend/tests/test_pdf_to_word_fidelity_report.py \
  backend/tests/test_model_eval_runner.py \
  -q
```

结果：`31 passed`

我还补做了 CLI 端到端 smoke：

1. 用 `quality_ready_contract.json` 生成 `visual_similarity.json`
2. 把该 artifact path 注入 fidelity input
3. 再跑 `--fidelity-final-report`

结果：

- `pass=True`
- `overall_score=97.8`
- `dimensions.visual_similarity.status=pass`

说明“canonical artifact 生成 → 最终 95% consumer 消费”这条链路已经可跑通。

## 边界说明
当前实现仍然基于 structured / precomputed visual facts contract；真实 PDF/DOCX render-pair generation 与 selective slow-model review 仍是后续工作。但这条边界已经在：

- `implementation_status`
- `known_gaps`
- `downstream_required_work`
- final report 的 `visual_similarity_artifact_not_ready`

这些字段里被明确表达，当前不会再把 contract-only stub 静默当成“文件缺失”或默认通过。

## 非阻塞说明
- 当前任务目录没有 `verify.json`；但不影响本次 review 通过，因为补丁、tests 和 CLI smoke 证据已经足够。

## 结论
本轮实现已经满足“打通 canonical visual similarity artifact 与最终 fidelity 消费链路”的任务目标，**可以进入 QA 重跑 PDF 转 Word 最终 95% 判定**。
