# 数学试卷 Paddle 补样解阻方案

生成时间：2026-05-17 13:59:59 +08:00

## 1. 事实核验

### 1.1 原 blocked 结论在当时是真实的
- 上游任务 `补齐数学试卷Paddle归档样例` 已在 `2026-05-17T12:38:54+08:00` 写入 `blocked` 结果。
- 其结论与当时的归档/报告一致：`phase3-paddle-quality/数学试卷/profile-audits.json` 与 `report.json` 在 `2026-05-17 11:29:01 +08:00` 生成，仍把 `paddleocr_vl` 记为 `candidate_count=0`，并提示 `缺少归档 source_dir`。
- `final-archive/profiles/paddleocr_vl/profile_manifest.json`、`archive_manifest.json`、`README.md` 和 `数学试卷/source_manifest.json` 都是 `2026-05-15 21:47:55 +08:00`，仍明确写着 `数学试卷` 缺失 Paddle 原始样例。

### 1.2 但当前文件系统已不再是“只有占位目录”
- 现在 `final-archive/profiles/paddleocr_vl/数学试卷/` 下已经存在：
  - `metrics.json`
  - `pages.jsonl`
  - `output.docx`
  - `warnings.json`
  - `source_manifest.json`
- 其中前四个文件的时间戳均为 `2026-05-17 13:32:11 +08:00`，晚于上游 blocked 结论和现有 Phase 3 报告。
- `metrics.json` 显示：
  - `total_seconds=4153.1542`
  - `page_count=12`
  - `avg_per_page≈346.10s`
  - `max_page=1343.9164s`
  - `peak_memory_mb=12254.031`
- 以 Phase 3 实际触发页 `1/8/9/11` 估算，这 4 页对应 `per_page_seconds` 总和约 `2194.58s`，平均约 `548.64s/页`。这说明“当前机器短时窗口内跑不完”仍成立，但也说明某次运行已经产生了真实文件，而不是纯占位。

### 1.3 当前真正的不一致点是 provenance 和消费链路未闭环
- `source_manifest.json` 仍然写 `source_dir=null`，并把样例标记为缺失。
- `profile_manifest.json` / `archive_manifest.json` / `README.md` 也仍把该样例视为缺失。
- `backend/tests/test_hybrid_e2e.py` 的 artifact 读取逻辑虽然已支持 `profile_manifest` overlay，但仍然依赖 `sample.source_dir` 去读取 `pages.jsonl` / `metrics.json` / `warnings.json`。
- 目前 `artifacts/pdf2word/model-eval/` 下找不到对应的 `paddleocr_vl/数学试卷` 源目录，因此这批 `13:32` 新文件还没有可追溯的来源目录。
- 从 `13:32` 的 `pages.jsonl` 做静态统计可见，触发页 `1/8/9/11` 上至少包含 `48 image + 2 table + 1 formula_candidate = 51` 个候选型 block。
  - 这是基于 `pages.jsonl` 的推断，不等同于已重新生成的 `profile-audits.json`。
  - 但它足以说明：一旦按真实来源刷新 manifest 和 Phase 3 报告，`candidate_count` 几乎不可能继续是 `0`。

## 2. blocker 真实状态判定

当前 blocker 不应再被表述为“数学试卷完全没有 Paddle 真实产物”。

更准确的表述是：

1. `2026-05-17 12:38` 之前，`当前机器 CPU 上长时间 Paddle 推理难以在任务时限内完成并沉淀可消费样例` 这个 blocker 是真实的。
2. 到 `2026-05-17 13:32`，归档目录里已经出现一批新的 Paddle 样例文件，说明“完全无产物”这一事实已经过时。
3. 但由于 `source_dir/provenance/manifest/Phase 3 report` 都没同步刷新，当前新的主 blocker 已转成：
   - 产物来源不可追溯
   - 报告与文件系统不一致
   - e2e / Phase 3 仍无法按正式链路消费这批新产物

所以，当前问题更像“归档一致性和 provenance 闭环未完成”，而不是单纯“算力还没跑出来”。

## 3. 四条路径对比

| 路径 | 前提条件 | 预期收益 | 主要风险 | 是否满足当前 blocked 任务原始验收 |
| --- | --- | --- | --- | --- |
| 1. 继续在当前机器上给更长 Paddle 推理窗口 | 允许至少 `45-90` 分钟级窗口；机器可稳定提供约 `12.3GB+` 内存；接受 CPU 长时间占用 | 不需要换环境，最贴近原执行环境；如果成功可补齐真实来源目录 | 现有证据显示耗时重、页间波动大，且此前已经出现“长时间无单页结果”现象；再跑一次仍可能卡住或无可复核沉淀 | 只有在真正产出可追溯 `source_dir` 并刷新 Phase 3 报告后才满足。单纯“再等更久”本身不满足 |
| 2. 换更快设备/外部已有算力重跑真实样例 | 有更快 CPU/GPU 或现成算力；允许复制 PDF 和产物；能记录环境、命令、时间戳 | 最有机会得到可复现、可追溯的正式源目录；比路径 1 更可能一次性收口 | 环境漂移、成本、权限与数据流转管理；仍需把 provenance 写回 manifest | 是。只要把真实输出放到新 `source_dir` 并刷新 manifest/report，即可满足 |
| 3. 接受降级补样 | PM/owner 明确把目标收紧为“能用于 Phase 3 候选评估即可”；允许 `pages.jsonl/metrics.json/warnings.json` 成为主交付，不强制要求完整原始 run 语义 | 如果接受 `13:32` 新文件为可信样例，可最快结束“纯 artifact gap”问题 | 会把“真实原始 run 归档”降级成“可消费候选样例”；若 provenance 仍缺失，未来报告和归档语义继续不干净 | 默认不满足原始验收；只有在 PM/owner 明确修改验收口径后才可视为满足 |
| 4. 接受保留缺口并固化 known gap | owner 接受 Paddle 在数学试卷样例上继续缺失；后续路线不再依赖该样例做 Paddle 正向结论 | 零新增算力、零新增执行成本 | `13:32` 新文件与旧 manifest/report 的矛盾必须另行处理；Paddle 在 image-dense 数学试卷上的证据仍不完整，相关结论继续偏弱 | 不满足原始验收 |

## 4. 推荐结论

### 4.1 不建议按“原 blocked 任务原样 + 当前机器加时”直接重开
- 原因不是它绝对跑不出来，而是当前已经出现了一批新产物，问题重心已从“完全无文件”转为“来源和元数据未闭环”。
- 在这种情况下，直接回到路径 1 重跑，很可能重复消耗数十分钟到数小时，却仍然没有解决 provenance 和报告一致性问题。

### 4.2 推荐动作分两段

#### 推荐动作 A：先做一次短平快 provenance 判定
由 PM 先确认 `2026-05-17 13:32:11` 这批新文件是谁生成的、从哪里生成的、是否就是目标 Paddle 真实运行产物。

如果答案是“能补证”：
- 不要重开原来的长跑 blocked 任务。
- 改为新开一个更小的执行任务，建议类似：
  - `刷新数学试卷Paddle归档provenance并重生成Phase3报告`
- 该任务只做：
  - 为 `13:32` 新文件补一个可追溯的 `source_dir`
  - 更新 `source_manifest.json`
  - 更新 `profile_manifest.json`
  - 重新生成 `phase3-paddle-quality/数学试卷/profile-audits.json` 与总 `report.json`
  - 必要时补 `archive_manifest.json` / `README.md` / hash 记录
- 这是当前最优先、成本最低、也最符合现状的收口路径。

如果答案是“无法补证，或文件不可信”：
- 不要继续把这批文件视作正式验收依据。
- 此时再考虑重开原 blocked 任务，但应直接走路径 2，而不是路径 1。

#### 推荐动作 B：若必须重跑，优先走更快设备/外部算力
- 重开条件：
  - 无法为 `13:32` 文件补充真实 provenance
  - owner 仍要求满足原 blocked 任务的“完整可复核样例 + Phase 3 刷新”验收
- 在这个前提下，最推荐的不是“当前机器再等更久”，而是：
  - 换更快设备/外部已有算力
  - 并同步记录 run label、环境、命令、输入 PDF、输出哈希和时间戳

## 5. 对 PM 的明确决策建议

1. 原 blocked 任务不值得按原样直接重开。
2. 先判断 `13:32` 新产物能否补齐 provenance。
3. 若能补齐，开一个“小范围 provenance + manifest + Phase 3 刷新任务”，不要再重复长时间 Paddle 计算。
4. 若不能补齐，再重开原任务，但重开条件应改为“有更快设备/外部算力可用”，而不是“继续在当前机器上盲目加时”。
5. 降级补样只适合作为 owner 明确改口径后的备选方案。
6. 接受 known gap 只适用于 owner 明确决定不再追求 Paddle 在该样例上的证据闭环。

## 6. 建议的后续任务验收点

如果走“provenance + 刷新”小任务，建议验收最少包含：

1. `数学试卷` 的 `source_manifest.json` 不再是 `source_dir=null`。
2. `profile_manifest.json` / `archive_manifest.json` / `README.md` 与真实文件状态一致。
3. `phase3-paddle-quality/数学试卷/profile-audits.json` 不再是“纯 artifact gap”状态。
4. 总 `report.json` 中 `数学试卷` 的 `paddleocr_vl` 不再显示 `candidate_count=0`，或若仍为 0，必须能用真实刷新结果证明，而不是因为缺目录。
5. 至少记录一次文件 hash 或等价 provenance 记录，避免后续再次出现“目录里有文件、报告里说没有”的分叉。
