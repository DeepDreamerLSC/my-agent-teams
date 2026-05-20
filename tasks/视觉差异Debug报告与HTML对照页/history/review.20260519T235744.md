# 审查结论：request_changes

本轮**不通过**。

当前交付已经把“总览页 + 逐页详情页 + key-region crop + 失败原因”这套 HTML 结构搭起来了，demo 也覆盖了科学 / 数学 / 英语 / 语文四个学科方向；但还有两处核心契约没接上，导致它**还不能直接复用于真实 visual_similarity / render_pair 产物**，所以我不能放行。

## 我确认已经做对的部分

1. **HTML debug 视图结构完整**
   - 有 `index.html`
   - 有 `pages/page-001..004.html`
   - 总览页能看到每页 source / output / diff 预览
   - 详情页能看到失败原因、blockers、vetoes、key-region crop

2. **跨学科 demo 已覆盖**
   - 科学
   - 数学
   - 英语
   - 语文

3. **本地可直开这件事方向是对的**
   - data URI placeholder 路径可以直接在 HTML 中渲染
   - 页面链接和结构对 PM / QA 来说是直观的

4. **现有测试能通过**
   - 本地复跑：`3 passed, 4 warnings`

## 阻塞问题

### 1) 还不能直接消费 canonical `visual_similarity` artifact
当前 `build_visual_diff_report()` 顶层只读：
- `payload["pages"]`

但上游已经冻结的真实视觉证据契约不是这个形状，而是：
- `render_pairs`
- `page_scores`
- `key_regions`
- `vetoes`

我直接拿上游 fixture：
- `quality_ready_contract.json`

去喂当前实现，结果是：
- `page_count = 0`
- `subject_scope = []`
- `pages = []`

也就是说，**真实 canonical artifact 进来后会直接生成空报告**。

这会导致当前 debug 视图虽然有 demo，但还不能接到真实 no-go 样例排查链路里。

### 2) key-region crop 字段名没对齐上游契约
上游 `visual_similarity` 的 canonical key region 字段里，输出裁切和 diff 图使用的是：
- `docx_crop_path`
- `diff_image_path`

但当前 `_normalize_key_regions()` 只识别：
- `output_crop_path`
- `diff_crop_path`

我本地 smoke 复现后，结果里的：
- `output_crop_uri = None`
- `diff_crop_uri = None`

这意味着即使真实 visual_similarity artifact 里已经带了裁切证据，当前 HTML 也会把**输出 crop / diff crop 丢掉**，关键排查价值就打折了。

### 3) 测试没有拦住上面两类问题
当前 3 条测试只覆盖了：
- bespoke `pages[]` payload
- placeholder demo HTML

但没有任何一条测试：
- 直接消费 canonical `quality_ready_contract.json`
- 验证 `docx_crop_path` / `diff_image_path` 能落到 HTML/JSON

所以现在测试绿了，但**真实集成路径其实还是断的**。

## 最小返修口径

建议按最小范围补这三点：

1. **补 canonical artifact 归一化入口**
   - 能直接吃 `visual_similarity` artifact
   - 自动把 `render_pairs + page_scores + key_regions + vetoes` 按页聚合成 debug report

2. **补字段兼容**
   - `docx_crop_path` → `output_crop_*`
   - `diff_image_path` → `diff_crop_*`
   - 同时保留对当前 `output_crop_path` / `diff_crop_path` 的兼容

3. **补回归测试**
   - 一条直接消费 canonical `quality_ready_contract.json`
   - 一条验证 `docx_crop_path` / `diff_image_path` 不会丢失

## 非阻塞提醒

1. 当前任务目录没有顶层 `verify.json`
2. 当前 `demo-cross-subject` 仍然是 placeholder 演示页；等 canonical 接线补齐后，建议再跑一组真实 no-go 样例，方便 PM/QA 直接看真实差异

## 建议下一步

- `recommended_next_action = dev`
