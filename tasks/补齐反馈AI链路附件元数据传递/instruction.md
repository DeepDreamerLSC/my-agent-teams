# 任务：补齐反馈AI链路附件元数据传递

## 背景
依赖上游后端契约任务：
- `/Users/lin/Desktop/work/my-agent-teams/tasks/补齐反馈附件详情契约与元数据返回`

生产排查已确认：当前 feedback AI 输入完全不包含附件信息，因此即使附件存在，AI 也看不到。

## 你的任务
补一版最小 AI 传递链路：
1. 在 feedback AI input_json 中带上附件元数据（至少文件名 / mime / file_id）
2. 若当前系统已有可用的 extracted_text / parse 结果，可按最小范围带摘要；若没有，不强做解析系统
3. 不破坏现有无附件场景

## 边界
- 先做元数据透传，不扩展复杂文件解析流程

## 交付物
完成后写 result.json，说明：
- 带入了哪些附件字段
- 无附件场景是否兼容
- 测试命令与结果
