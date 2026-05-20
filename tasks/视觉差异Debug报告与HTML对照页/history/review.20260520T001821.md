# 审查结论：request_changes

本轮**不通过**。

先说结论：这轮修复把我上一轮指出的**主逻辑问题**基本补上了——
- 已支持 canonical visual_similarity 页聚合
- 已兼容 `docx_crop_path` / `diff_image_path`
- 本地 pytest 和 end-to-end smoke 都能跑通

但现在出现了一个新的阻塞：**测试本身依赖临时 worktree 的本机绝对路径**，所以这份交付还不能作为稳定可合并结果放行。

## 我确认已经做对的部分

1. **canonical visual_similarity 不再是空报告**
   - `build_visual_diff_report()` 已新增 `_collect_pages()` / `_normalize_canonical_visual_similarity_pages()`
   - 能按页聚合 `render_pairs / page_scores / key_regions / vetoes`

2. **crop 字段兼容已补齐**
   - `docx_crop_path -> output_crop_path`
   - `diff_image_path -> diff_crop_path`
   - 现有 `output_crop_path / diff_crop_path` 也仍兼容

3. **本地回归能过**
   - `py_compile`：通过
   - `pytest`：**5 passed, 4 warnings**

4. **end-to-end smoke 也成立**
   - 我用 `visual_similarity_gate` 基于 canonical fixture 先生成 gate artifact，再喂给 `build_visual_diff_report()`
   - 结果 page-level source/output/diff 和 key-region output/diff crop 都能正确落成 `file://` URI
   - 说明这轮代码主逻辑基本是对的

## 阻塞问题

### 测试依赖了临时 worktree 的绝对路径
当前测试文件里：
- `CANONICAL_FIXTURE_ROOT`
- `QUALITY_READY_CONTRACT_PATH`
- `QUALITY_READY_RENDER_PAIR_PATH`

被直接写成了：
- `/Users/linsuchang/Desktop/work/my-agent-teams/.runtime/worktrees/chiralium/visual_similarity-be6f0714/...`

这有两个问题：

1. **不是目标仓库里的稳定测试资产**
   - 它依赖另一个 task 的 runtime worktree
   - worktree 清掉后，这条路径就没了

2. **不是可移植的测试输入**
   - 换一台机器
   - 换一个 checkout 路径
   - 或者进 CI
   这组测试都可能直接炸掉

也就是说，当前 `5 passed` 只是“**在这台机器、这个 runtime 布局下**通过”，还不能证明它是稳定门禁。

## 最小返修口径

建议按最小范围修：

1. **移除测试里的绝对路径依赖**
   - 不要再读 `.runtime/worktrees/...`

2. **把 canonical fixture 最小数据自给化**
   - 最简单方式：直接把测试需要的最小 canonical payload / render_pair payload 内联到当前测试文件 helper 里
   - 或改为读取目标仓库内稳定存在的 fixture 路径

3. **保证 pytest 只依赖仓库自身即可运行**
   - worktree 被清理后还能跑
   - 换路径、换机器还能跑

## 非阻塞提醒

1. 当前任务目录还没有顶层 `verify.json`
2. `demo-cross-subject` 仍是 placeholder 演示页，不是真实 no-go 样例重跑结果；当前不阻塞，但后续若要给 PM/QA 演示真实排查体验，建议再单独重生一轮

## 建议下一步

- `recommended_next_action = dev`
