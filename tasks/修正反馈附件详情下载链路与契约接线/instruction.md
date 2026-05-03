# 任务：修正反馈附件详情下载链路与契约接线

## 背景
原任务：
- `/Users/lin/Desktop/work/my-agent-teams/tasks/补充反馈详情页附件展示与下载入口`

审查意见：
- `/Users/lin/Desktop/work/my-agent-teams/tasks/补充反馈详情页附件展示与下载入口/review.md`

当前阻塞点不是“有没有附件区”，而是：
1. 当前直接把受保护的 `/api/files/{id}` 裸链接塞给 `<a href>`，真实环境大概率 401
2. 前端 service 层 DTO 也没有正式补 `attachments` 字段，页面靠局部类型断言在接
3. 测试没有覆盖受保护下载链路

## 你的任务
请做最小补修：

### A. 复用现有受保护文件下载链路
- 不要继续让反馈详情页直接用裸 `/api/files/{id}` 作为最终下载入口
- 先找项目中**已正常工作的受保护附件下载实现**做参照（审查已指向 `MessageBubble.tsx`）
- 复用同类模式：优先签名/下载链接，必要时 blob fallback
- 确保“打开/下载”在真实鉴权场景下可用

### B. 正式补齐前端 DTO 契约
- 在 `feedbackManagement.ts` 中补 `attachments` 字段
- 不要继续只靠页面局部类型断言读取 `attachments`

### C. 补测试
至少覆盖：
1. 问题详情页“有附件”时展示并可走受保护下载链路
2. 需求详情页“有附件”时展示并可走受保护下载链路
3. 无附件时安全不渲染
4. 不是只断言 `<a href>` 存在，而是要验证采用了正确下载策略

## 边界
- 只改 write_scope 内文件
- 不扩展复杂预览器
- 不改后端 detail 契约

## 交付物
完成后写：
- `/Users/lin/Desktop/work/my-agent-teams/tasks/修正反馈附件详情下载链路与契约接线/result.json`

请在 result.json 中说明：
- 参考了哪条现有受保护下载实现
- 最终采用的下载方式
- DTO 契约如何补齐
- 测试命令与结果
