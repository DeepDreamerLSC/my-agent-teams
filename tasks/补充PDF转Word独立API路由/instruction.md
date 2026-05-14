# 任务：补充 PDF 转 Word 独立 REST API 路由

## 任务类型
development — 为已有的 PDF 转 Word 服务层补充独立的 HTTP API 路由

## 目标
为 `PDFConversionService` 暴露一个独立的 REST API endpoint，使外部调用方可以直接通过 HTTP POST 上传 PDF 并下载转换后的 DOCX，无需走 chat/skill 通道。

## 任务边界
- 新建 `backend/app/api/pdf_to_word.py`，包含 API 路由
- 修改 `backend/app/api/__init__.py`，注册新模块
- 修改 `backend/app/main.py`，include_router 注册路由
- 新建 `backend/tests/test_pdf_to_word_api.py`，覆盖 API 测试
- 不修改 `backend/app/services/pdf_to_word/` 下的任何服务层代码

## 输入事实
- 服务层已实现：`backend/app/services/pdf_to_word/conversion_service.py` 中有 `PDFConversionService.convert()` 异步方法，接受 `pdf_path`，返回转换结果
- 现有 API 模式参考：`backend/app/api/stt.py`（文件上传+权限+日志的模式）
- 路由注册模式：在 `backend/app/main.py` 中通过 `app.include_router(xxx.router, prefix="/api", tags=[...])` 注册
- 权限系统：使用 `app.core.deps.get_current_user` + `app.services.permission_service.require_permission`
- 文件上传：使用 FastAPI 的 `UploadFile = File(...)`

## 约束
- write_scope: `backend/app/api/pdf_to_word.py`, `backend/app/api/__init__.py`, `backend/app/main.py`, `backend/tests/test_pdf_to_word_api.py`
- read_only: false
- 依赖上游任务: 无
- target_environment: dev
- execution_mode: dev
- owner_approval_required: false
- 禁止修改 `backend/app/services/pdf_to_word/` 下的任何文件

## API 设计要求
1. `POST /api/pdf-to-word/convert` — 上传 PDF，返回转换后的 DOCX 文件流（`StreamingResponse`，content-type `application/vnd.openxmlformats-officedocument.wordprocessingml.document`）
   - 入参：`file: UploadFile`（仅接受 `.pdf`），可选 `mode: str = "balanced"`，可选 `parser_backend: str = "auto"`
   - 权限：`require_permission("pdf_to_word.use")` 或复用已有文件权限
   - 响应：直接返回 DOCX 文件流，带 `Content-Disposition: attachment; filename="xxx.docx"`
   - 错误：非 PDF 返回 400，转换失败返回 500
2. `GET /api/pdf-to-word/health` — 健康检查，返回服务可用状态

## 交付物
1. `backend/app/api/pdf_to_word.py` — API 路由文件
2. `backend/app/api/__init__.py` — 已更新注册
3. `backend/app/main.py` — 已添加 include_router
4. `backend/tests/test_pdf_to_word_api.py` — API 级别测试（健康检查、正常转换、非 PDF 拒绝、无文件拒绝）

## 验收标准
1. `POST /api/pdf-to-word/convert` 可以上传 PDF 并下载 DOCX
2. `GET /api/pdf-to-word/health` 返回服务状态
3. 非 PDF 文件上传返回 400
4. API 有权限保护，未登录用户返回 401
5. 测试通过：`pytest backend/tests/test_pdf_to_word_api.py`
6. 不修改任何 `backend/app/services/pdf_to_word/` 下的文件
7. 遵循项目现有 API 代码风格（参考 `stt.py`）

## 下游动作
完成后进入 review（review-1），通过后 QA 验证，最终 PM 收口。
