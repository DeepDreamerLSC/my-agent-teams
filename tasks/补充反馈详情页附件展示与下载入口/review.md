# Code Review - 补充反馈详情页附件展示与下载入口

## 结论
- **审查结论：驳回（REQUEST CHANGES）**
- 依据：`instruction.md`、`result.json`、相关代码实现、现有受保护附件下载实现对照审查。
- 说明：任务目录当前**无 `verify.json`**；本次结论基于代码与工件审查给出，未自行执行功能测试。

## 阻塞问题

### 1. 附件“打开/下载”直接走裸 `/api/files/{id}`，未复用现有受保护下载链路，真实环境大概率 401
- 位置：
  - `/Users/lin/Desktop/work/chiralium/frontend/src/pages/feedback/FeedbackIssuesPage.tsx:72-100,305`
  - `/Users/lin/Desktop/work/chiralium/frontend/src/pages/feedback/FeedbackRequestsPage.tsx:72-100,349`
- 当前实现把后端返回的 `attachment.download_url` 直接放进 `<a href>`：
  - `打开`：`<a href={attachment.download_url} target="_blank" ...>`
  - `下载`：`<a href={attachment.download_url} download={attachment.file_name}>`
- 但后端 `/api/files/{file_id}` 下载接口不是公开链接，而是受鉴权保护：
  - `/Users/lin/Desktop/work/chiralium/backend/app/api/files.py:222-253`
  - `/Users/lin/Desktop/work/chiralium/backend/app/core/deps.py:31-38`
- 项目前端 Bearer token 注入只发生在 axios 拦截器内，普通 `<a>` 导航不会复用这层鉴权：
  - `/Users/lin/Desktop/work/chiralium/frontend/src/services/api.ts:5-16`
- 现有已工作的受保护附件下载参考实现也明确不是直接跳裸链接，而是：
  1. 先请求 `/files/{id}/download-link`
  2. 再使用签名链接下载
  3. 失败时退回 axios blob 下载
  - 参考：`/Users/lin/Desktop/work/chiralium/frontend/src/components/MessageBubble.tsx:61-63,217-246`
  - 对应测试：`/Users/lin/Desktop/work/chiralium/frontend/src/test/messageBubbleActions.test.tsx:123-145`
- 影响：当前页面虽然出现了“打开/下载”入口，但在真实受保护文件场景下很可能无法正常打开/下载，不满足任务“至少支持下载/打开入口”的目标。
- 修改建议：复用现有受保护附件下载模式；至少不要直接把 `/api/files/{id}` 暴露给 `<a>` 作为最终入口。

## 非阻塞观察项

### 2. 前端服务层 DTO 未补齐 `attachments`，页面靠局部类型 + 强转读取，存在契约漂移风险
- 位置：
  - 页面本地定义：
    - `/Users/lin/Desktop/work/chiralium/frontend/src/pages/feedback/FeedbackIssuesPage.tsx:24-30,305`
    - `/Users/lin/Desktop/work/chiralium/frontend/src/pages/feedback/FeedbackRequestsPage.tsx:26-32,349`
  - 服务层缺失字段：
    - `/Users/lin/Desktop/work/chiralium/frontend/src/services/feedbackManagement.ts:59-90`
  - 后端实际已稳定返回 `attachments`：
    - `/Users/lin/Desktop/work/chiralium/backend/app/api/feedback.py:40-45,110-152,213-280`
- 当前页面通过 `(detail as FeedbackIssueDetail & { attachments?: ... }).attachments` 读取数据，短期可工作，但会让前后端契约长期不一致。
- 建议：把 `attachments` 正式补入 `FeedbackIssueDetail` / `FeedbackRequestDetail`，避免重复定义与类型断言扩散。

## 测试审查
- `/Users/lin/Desktop/work/chiralium/frontend/src/test/feedbackAttachmentDetails.test.tsx:52-114`
- 已覆盖：
  - 问题详情页有附件时展示文件名与入口
  - 需求详情页无附件时不报错、不渲染附件区
- 未覆盖：
  - 受保护文件真实下载链路是否可用
  - 是否复用签名下载链接 / blob fallback
  - 需求详情页“有附件”时是否同样正确展示文件名与打开/下载入口
  - 问题详情页“无附件”时是否安全不渲染附件区
- 因此当前测试不足以兜住本次阻塞问题。

## 最终意见
当前实现完成了“UI 上出现附件区”的一半目标，但**未接入项目现有受保护文件下载契约**，打开/下载入口存在实际不可用风险，暂不建议合入。
