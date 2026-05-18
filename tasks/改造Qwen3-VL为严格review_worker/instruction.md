# 任务：改造 Qwen3-VL 为严格 review worker

## 任务类型
development（prompt + schema 重构）

## 目标
将 Qwen3-VL 从"OCR parser"定位改造为"strict review worker"：不再输出正文 blocks，只输出结构化审查结果。

## 任务边界
- 改造 prompt template（qwen3_vl_page_review.md）
- 增强 vlm_review_json.py normalizer 的 schema 校验
- 可调整 inference_config.yaml 中 qwen3_vl_8b profile 参数
- 不修改框架代码（VLMReviewAdapter 基类）

## 输入事实
- 当前 prompt：parser_adapters/prompts/qwen3_vl_page_review.md
- 当前 normalizer：parser_adapters/normalizers/vlm_review_json.py
- 横评发现：45 条 JSON/bbox 警告，正文 block 覆盖不足，不适合作 parser
- Qwen3-VL 服务：127.0.0.1:18111，权重 .runtime/models/qwen3-vl-8b-3bit
- Python 3.12 venv：/Users/linsuchang/Desktop/work/chiralium/.venv-mlx/

## 新 JSON Schema
```json
{
  "page_review": {
    "page_number": int,
    "issues": [
      {
        "issue_type": "missing_question | duplicate_question | wrong_order | material_mismatch | image_unassigned | formula_misidentified | low_confidence_text",
        "source_block_ids": ["..."],
        "question_id": "... | null,
        "suggested_action": "insert | remove | reorder | reassign | flag_for_review",
        "confidence": 0.0-1.0,
        "detail": "..."
      }
    ],
    "confidence_summary": {
      "overall": 0.0-1.0,
      "question_sequence_ok": bool,
      "layout_quality": "good | acceptable | poor"
    }
  }
}
```

## 交付物
1. 重写 prompts/qwen3_vl_page_review.md
2. 增强 normalizers/vlm_review_json.py（schema 校验 + 错误处理）
3. 5 样例验证：json_valid_rate ≥ 80%

## 约束
- write_scope 以 task.json 为准
- 不修改 VLMReviewAdapter 基类或其他 normalizer
- 新 prompt 必须保持 OpenAI-compatible vision API 调用格式

## 验收标准
1. 新 prompt 输出严格 JSON，不包含正文 blocks
2. normalizer 有 schema 校验，解析失败不崩溃
3. json_valid_rate ≥ 80%（首轮目标）
4. result.json 包含新旧对比数据

## 下游动作
完成后 review worker 可用于 hybrid_experimental 管线。
