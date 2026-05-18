# 任务：补评 GLM-4.6V-Flash 模型横评

## 任务类型
development（环境部署 + 评估执行）

## 目标
等 MLX 权重缓存完成后，在 M5 Max 上部署 GLM-4.6V-Flash 本地推理服务，用 VLMReviewAdapter 跑 5 个样例与 apple_baseline 对比。

## 任务边界
- 部署 GLM-4.6V-Flash 推理服务（MLX，使用 .venv-mlx）
- 配置 inference_config.yaml
- 用 model_eval_runner 跑批
- 不修改框架代码

## 输入事实
- Python 3.12 + mlx-vlm 0.5.0 环境：/Users/linsuchang/Desktop/work/chiralium/.venv-mlx/
- MLX 权重已完整下载到：/Users/linsuchang/Desktop/work/models/glm-46v-flash-4bit/（6.6G，shard 1+2 完整）
- VLMReviewAdapter 已实现，通过 OpenAI-compatible vision API 调用
- prompt template：prompts/glm_vl_page_review.md
- normalizer：normalizers/vlm_review_json.py
- 架构方案端口建议：GLM-4.6V-Flash 端口 18121
- 基线数据：artifacts/pdf2word/model-eval/20260514-144102/apple_baseline/
- 归档样例：artifacts/pdf2word/final-archive/profiles/apple_baseline/（含 5 样例标准化路径）
- GLM-4.6V-Flash 是通用 VLM，非专用 OCR 模型，作为 VLM review 对照
- inference_config.yaml 中 GLM profile 路径需更新为新模型目录

## 约束
- write_scope 以 task.json 为准
- 推理后端用 MLX（.venv-mlx），不用系统 Python 3.9
- 必须通过 model_eval_runner 跑批
- 模型缓存到 HuggingFace 默认缓存目录
- 模型权重已完整下载，无需等待

## 交付物
1. GLM-4.6V-Flash 推理服务（端口 18121）
2. inference_config.yaml 更新
3. 5 样例跑批 + 对比报告
4. 如模型不可用，result.json 说明原因

## 验收标准
1. 推理服务可正常启动
2. create_adapter('glm_46v_flash').is_available() 返回 True
3. 5 个样例全部跑完
4. 有对比报告
5. 如模型不可用，result.json 说明原因

## 下游动作
完成后数据补入横评汇总。GLM-4.6V-Flash 定位为 VLM review 对照，不阻塞 hybrid 管线开发。
