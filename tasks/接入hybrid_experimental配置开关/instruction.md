# 任务：接入 hybrid_experimental 配置开关

## 任务类型
development

## 目标
修改配置和 registry 支持 `parser_backend=hybrid_experimental`，增加 Skill/API 参数透传。

## 任务边界
- 修改 inference_config.yaml 增加 hybrid_experimental profile
- 修改 registry.py 支持 hybrid backend resolve
- `auto` 不指向 hybrid
- 测试 backend resolve、mock/apple 不回归

## 输入事实
- 设计文档：design/pdf2word/hybrid_experimental增强管线设计.md（Section 2-3）
- 现有 inference_config.yaml 已有 7 个 backend 和 6 个 profile
- 现有 registry.py 有 create_adapter()、create_backend()
- hybrid_experimental 不替换默认 apple backend

## 约束
- write_scope 以 task.json 为准
- 不修改 Adapter 基类或 normalizer
- 不修改 apple_baseline profile
- hybrid_experimental 默认不启用，需显式指定

## 交付物
1. inference_config.yaml 新增 hybrid_experimental profile 配置
2. registry.py 支持 hybrid backend resolve
3. 测试文件：test_hybrid_backend_resolve.py
4. result.json 包含 resolve 测试结果

## 验收标准
1. create_adapter('hybrid_experimental') 能正常返回
2. apple/auto profile 不受影响
3. 测试通过

## 下游动作
完成后进入 hybrid_experimental 管线后续任务（候选过滤、PageIR 合并等）。
