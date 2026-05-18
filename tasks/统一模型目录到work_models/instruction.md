# 任务：统一模型目录到 work/models

## 任务类型
development（基础设施整理）

## 目标
将所有横评模型统一迁移到 `/Users/linsuchang/Desktop/work/models/`，更新所有引用路径。

## 任务边界
- 迁移模型文件
- 更新 inference_config.yaml 中的模型路径
- 更新 .env 中的模型路径
- 更新 HuggingFace 缓存配置（HF_HOME 或 HF_CACHE_DIR）指向新目录
- 不修改框架代码逻辑，只改路径配置

## 当前模型分布

| 模型 | 当前位置 | 大小 | 目标位置 |
|------|---------|------|---------|
| Qwen3-VL-8B 3bit | `.runtime/models/qwen3-vl-8b-3bit/` (4.4GB) | → `work/models/qwen3-vl-8b-3bit/` |
| Qwen3-VL-8B 4bit | `.runtime/models/qwen3_vl_8b_4bit/` (1GB) | → `work/models/qwen3-vl-8b-4bit/` |
| GLM-4.6V-Flash 4bit | `~/.cache/huggingface/hub/models--mlx-community--GLM-4.6V-Flash-4bit/` (147MB+) | → `work/models/glm-46v-flash-4bit/` |
| PaddleOCR-VL | `/private/tmp/paddlex-cache/official_models/PaddleOCR-VL/` (2GB) | → `work/models/paddleocr-vl/` |
| Qwen3.5-122B | 已在 `work/models/Qwen3.5-122B-A10B-4bit/` | ✅ 不动 |

注意：
- `/Users/linsuchang/Desktop/work/chiralium/.runtime/models/qwen3-vl-8b/` (80MB) 是旧的占位目录，可删除
- HuggingFace 缓存目录 `~/.cache/huggingface/hub/` 中还有 PP-DocLayout、PP-OCRv5 等 PaddleX 模型（4KB 占位），也一并迁移或重新指向

## 约束
- write_scope 以 task.json 为准
- 迁移前确保相关推理服务已停止（Qwen3-VL 端口 18111）
- 用 `mv` 而非 `cp` 避免占用双倍空间
- 如果模型正在被使用，先停止服务再迁移
- PaddleOCR-VL 在 /private/tmp 下，重启会丢失，必须迁移到持久目录

## 交付物
1. 所有模型统一到 `/Users/linsuchang/Desktop/work/models/`
2. inference_config.yaml 路径更新
3. .env 路径更新
4. result.json 列出迁移前后路径对照表

## 验收标准
1. `/Users/linsuchang/Desktop/work/models/` 包含所有模型
2. inference_config.yaml 指向新路径
3. .env 指向新路径
4. 旧目录已清理（或保留为空）

## 下游动作
完成后所有后续任务和模型下载统一使用 `/Users/linsuchang/Desktop/work/models/`。
