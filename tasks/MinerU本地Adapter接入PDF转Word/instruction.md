# 任务：MinerU 本地 Adapter 接入 PDF 转 Word

## 任务类型
development — 为 PDF 转 Word 服务接入本地 MinerU CLI/Python adapter，替代当前 mock/fixture 和 PaddleOCR-only 方案

## 目标
在 Apple M5 Max 128GB 本地环境中，用 MinerU 替代当前 apple worker（PaddleOCR-only），实现真正的版面分析 + 公式识别 + 表格识别 + 图片提取，使扫描件 PDF 转 Word 质量达到可用水平。

## 任务边界
- 新建 `backend/app/services/pdf_to_word/mineru_client.py`，实现 MinerU 本地 adapter
- 修改 `backend/app/services/pdf_to_word/settings.py`，增加 MinerU 配置项
- 修改 `backend/app/services/pdf_to_word/conversion_service.py`，集成 mineru_client
- 修改 `backend/app/core/config.py`，增加 MinerU 环境变量
- 修改 `.env.example`（根目录和 backend 目录），增加 MinerU 配置模板
- 新建测试文件和 fixtures
- 不修改 `skill.py`，不修改 `workers/apple_pdf_worker/`

## 输入事实
- 当前 apple worker 只做 PaddleOCR 逐行文字识别，没有版面分析，扫描件数学试卷质量极差（34.4% 碎片、阅读顺序混乱、公式/图片/表格全部丢失）
- MinerU 是 OpenDataLab 的文档解析工具，支持版面分析（LayoutLM）+ 公式识别（UniMERNet）+ 表格识别 + 图片提取
- 目标环境：Apple M5 Max 128GB macOS，MinerU 支持 Apple Silicon
- MinerU 输出：content_list.json、middle.json、markdown、images 等
- 现有代码参考：`backend/app/services/pdf_to_word/parser_client.py`（已有 mock/apple backend 切换机制）
- 架构评估结论：`/Users/linsuchang/Desktop/work/my-agent-teams/tasks/评估M5Max本地运行MinerU与视觉模型方案/result.json`
- 原设计文档：`/Users/linsuchang/Desktop/work/chiralium/design/product/pdf-to-word-skill-mineru-minicpmv-design.md`

## 约束
- write_scope: `backend/app/core/config.py`, `backend/.env.example`, `.env.example`, `backend/app/services/pdf_to_word/settings.py`, `backend/app/services/pdf_to_word/mineru_client.py`, `backend/app/services/pdf_to_word/conversion_service.py`, `backend/tests/test_pdf_to_word_mineru_client.py`, `backend/tests/fixtures/pdf_to_word/mineru_content_list.json`, `backend/tests/fixtures/pdf_to_word/mineru_middle.json`
- read_only: false
- 依赖上游任务: 实现PDF转WordSkillMVP闭环（已完成）
- target_environment: dev
- execution_mode: dev
- owner_approval_required: false
- 不修改 skill.py，skill 仍只调用 PDFConversionService
- 不修改 workers/apple_pdf_worker/，保留为可选 fallback

## 配置项（需新增到 config.py 和 settings.py）
- `PDF_TO_WORD_PARSE_BACKEND=mock|apple|local_mineru_cli|local_mineru_python`（扩展，增加 local_mineru_cli 和 local_mineru_python）
- `MINERU_CLI_PATH`：MinerU CLI 可执行文件路径
- `MINERU_PYTHON_BIN`：MinerU Python 解释器路径
- `MINERU_MODEL_DIR`：MinerU 模型缓存目录
- `MINERU_WORKDIR`：MinerU 工作临时目录
- `MINERU_TIMEOUT_SECONDS`：超时时间（默认 300）
- `MINERU_PARSE_MODE`：解析模式

## 验收标准
1. 默认 dev backend 可配置为 `local_mineru_cli`；测试环境默认仍可使用 `mock`
2. MinerU adapter 以 per-job 临时目录调用本机 CLI/Python，读取 content_list/middle_json/markdown/images，并映射为 DocumentIR
3. 保留 `apple` 和 `mock` backend 作为可选分支，不做破坏性修改
4. 进程 timeout、非零退出码、缺少输出文件、JSON schema 缺字段都转为结构化错误或 warning；临时目录按策略清理
5. 新增 fixtures 固定 MinerU 样例输出（content_list.json、middle.json），单测覆盖 paragraph/table/image/formula block 映射
6. 不修改 skill.py 为重逻辑入口；skill 仍只调用 PDFConversionService
7. 测试通过：`pytest backend/tests/test_pdf_to_word_mineru_client.py`

## 前置步骤（dev 执行前需完成）
1. 在目标机器安装 MinerU：`pip install magic-pdf[full]` 或按官方文档安装
2. 下载 MinerU 模型权重（首次运行会自动下载）
3. 用 `/Users/linsuchang/Desktop/work/chiralium/example/扫描件 /数学试卷.pdf` 做一次 CLI smoke test，确认 MinerU 可以正常输出
4. 将真实 MinerU 输出固化为 fixtures

## 交付物
1. `backend/app/services/pdf_to_word/mineru_client.py` — MinerU adapter
2. `backend/app/services/pdf_to_word/settings.py` — 已增加 MinerU 配置
3. `backend/app/services/pdf_to_word/conversion_service.py` — 已集成 mineru_client
4. `backend/app/core/config.py` — 已增加环境变量
5. `.env.example` + `backend/.env.example` — 已更新配置模板
6. `backend/tests/test_pdf_to_word_mineru_client.py` — 单元测试
7. `backend/tests/fixtures/pdf_to_word/mineru_content_list.json` — fixture
8. `backend/tests/fixtures/pdf_to_word/mineru_middle.json` — fixture

## 下游动作
完成后进入 review（review-1），通过后用 `example/扫描件 /数学试卷.pdf` 端到端验证质量对比，确认版面分析、公式识别、表格识别、图片提取效果达标。
