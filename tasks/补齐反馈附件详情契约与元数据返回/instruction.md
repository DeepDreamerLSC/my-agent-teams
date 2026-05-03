# 任务：补齐反馈附件详情契约与元数据返回

## 背景
来自生产排查结论：
- `/Users/lin/Desktop/work/my-agent-teams/tasks/排查反馈管理未关闭问题根因/result.json`

B 号问题（反馈附件未保存或传递导致后续环节无法查看）的核心根因不是存储整体失效，而是：
- feedback detail/admin detail 当前只返回 `attachment_ids`
- 不返回可直接消费的附件元数据（文件名、mime、下载入口）
- 导致后续详情页与 AI 链路都无法真正消费附件

## 你的任务
请先完成后端最小契约修复：
1. feedback detail / admin detail 不再只返回 `attachment_ids`
2. 增加结构化 `attachments[]`，至少包含：
   - file_id
   - file_name / original_name
   - mime_type
   - download_url（或等价可下载字段）
3. 保持历史 `attachment_ids` 向后兼容，避免直接破坏旧调用方
4. 补测试覆盖详情接口输出

## 边界
- 先只做后端 detail 契约，不扩散到 AI 分析输入
- 不处理 A 号历史重复工单关闭动作

## 交付物
完成后写 result.json，说明：
- 新增了哪些附件字段
- 是否保持 attachment_ids 兼容
- 测试命令与结果
