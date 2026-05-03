# Code Review - 修正反馈附件详情下载链路与契约接线

## 结论
- **审查结论：驳回（REQUEST CHANGES）**
- 依据：`instruction.md`、`result.json`、代码实现、现有受保护下载链路与后端文件接口契约对照审查。
- 说明：任务目录当前 **无 `verify.json`**；本次结论基于代码与工件审查给出，未自行执行功能测试。

## 已修复项
1. **上轮“裸 `/api/files/{id}` 直接塞给 `<a>`”的阻塞点已修复**
   - 详情页已改为调用受保护下载函数，不再直接暴露裸链接：
     - `/Users/lin/Desktop/work/chiralium/frontend/src/pages/feedback/FeedbackIssuesPage.tsx:67-114,312`
     - `/Users/lin/Desktop/work/chiralium/frontend/src/pages/feedback/FeedbackRequestsPage.tsx:67-114,356`
   - 下载函数已改为优先请求 `/files/{id}/download-link`，失败时退回 axios blob：
     - `/Users/lin/Desktop/work/chiralium/frontend/src/services/feedbackManagement.ts:107-160`

2. **前端 DTO 契约已正式补齐**
   - `FeedbackAttachmentSummary` 已抽到 service 层；`FeedbackIssueDetail` / `FeedbackRequestDetail` 已新增 `attachments`：
     - `/Users/lin/Desktop/work/chiralium/frontend/src/services/feedbackManagement.ts:32-38,68-100`
   - 页面不再依赖局部重复类型与强制断言。

3. **测试覆盖比上一轮明显更完整**
   - 已补：问题详情有附件、需求详情有附件、无附件不渲染、下载策略断言：
     - `/Users/lin/Desktop/work/chiralium/frontend/src/test/feedbackAttachmentDetails.test.tsx:77-180`

## 阻塞问题

### 1. “打开”按钮在成功路径上仍然复用了下载链接，和“下载”没有真实语义区分
- 位置：
  - `/Users/lin/Desktop/work/chiralium/frontend/src/services/feedbackManagement.ts:132-147`
  - `/Users/lin/Desktop/work/chiralium/backend/app/api/files.py:103-119,237-279`
- 当前 `openFeedbackAttachment()` 的成功路径是：
  1. 先请求 `/files/{id}/download-link`
  2. 拿到签名 URL 后 `clickLink(signedUrl, { target: '_blank' })`
- 但后端签名链接最终落到 `/api/files/{id}/direct?token=...`，返回的响应头由 `_build_download_response()` 统一硬编码为：
  - `Content-Disposition: attachment; filename=...`
- 这意味着“打开”成功路径本质上仍然走的是**下载响应**；代码里并没有为“打开”提供和“下载”不同的服务端契约或前端策略。
- 当前只有签名失败时，才会退回 blob + object URL 新开窗口：
  - `/Users/lin/Desktop/work/chiralium/frontend/src/services/feedbackManagement.ts:137-146`
- 影响：本任务要求的是“下载/打开入口”都可用，但当前实现只能证明“受保护下载链路”已修好，**无法证明“打开”在主路径上真的成立**。
- 建议：
  - 要么把“打开”改成真正可打开的实现（例如基于 blob/object URL 的明确打开路径，或后端提供 inline/preview 契约）；
  - 要么如果产品接受仅下载，就不要继续保留误导性的“打开”按钮文案。

## 测试审查
- `/Users/lin/Desktop/work/chiralium/frontend/src/test/feedbackAttachmentDetails.test.tsx:77-180`
- 已覆盖：
  - 问题详情页有附件时优先走签名下载链路
  - 需求详情页签名失败时退回 blob 下载链路
  - 无附件时不渲染附件区
- 未覆盖：
  - “打开”按钮的主路径行为
  - “打开”在签名成功场景下是否真的与“下载”区分
- 因此，当前测试还不足以证明任务中“打开入口可用”这一点。

## 最终意见
这次补修已经解决了上轮最核心的**鉴权下载链路**与 **DTO 契约**问题，但“打开”按钮仍未形成可验证的独立行为，测试也没有覆盖该路径。当前状态更接近“下载可用、打开语义未完成”，因此暂不建议合入。
