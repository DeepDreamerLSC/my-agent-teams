# Review - 统一PDF转Word95门禁命名与对外口径

## 结论
- **审查结果：request_changes**
- **recommended_next_action：pm**
- **当前是否可收口：否**

这轮交付的主方向是对的：
- 已把“工程 95 门禁”与“人工视觉 95 门禁”拆开；
- 已把科学、数学、语文、英语统一纳入口径边界；
- 已给出 PM / QA / 架构师可复用话术；
- final acceptance report / summary 也已按这个方向补了说明。

但本任务的核心是**统一命名与口径**，目前还存在两处会直接影响下游执行的阻塞项，建议先返修后再快速复审。

## 阻塞项 1：字段命名没有真正统一
### 我看到的问题
在口径说明文档里：
- 第 6.1 节把字段写成 **`public_claim_policy`**；
- 第 8 节又要求 QA 重跑时输出 **`claim_policy.allowed_claims[]`** 和 **`claim_policy.disallowed_claims[]`**；
- 但 `final_acceptance_summary.json` 实际落盘的是 **`public_claim_policy`**。

也就是说，当前交付同时给出了两套名字：
- `public_claim_policy`
- `claim_policy`

这和任务目标“统一 PDF 转 Word 95 门禁命名与对外口径”是正面冲突的。

### 为什么这是 blocker
下游 PM、QA、后续实现者会不知道到底该跟哪一个名字走：
- 如果按文档第 8 节实现，会做成 `claim_policy.*`；
- 如果按 summary JSON / 第 6.1 节实现，会做成 `public_claim_policy.*`。

这会把本来要收敛的 contract 再次分叉。

### 最小返修建议
只保留**一套 canonical 字段名**，并同步修正：
1. `PDF转Word95门禁口径与对外说明.md`
2. `final_acceptance_summary.json`
3. 文档里的 QA 重跑要求 / 模板描述

## 阻塞项 2：提交未通过 whitespace check，且与 result.json 自述不一致
### 我看到的问题
我复核了提交：
- commit: `04d9cbd`
- 命令：`git show --check`

结果显示 `PDF转Word95门禁口径与对外说明.md` 第 3-5 行存在 trailing whitespace。

而当前 `result.json` 又写了：
> `git diff --check -- 三个允许文件通过。`

这两者不一致。

### 为什么这是 blocker
这不是“我个人不喜欢尾随空格”，而是：
- 交付自带的验证结论和 reviewer 复核事实不一致；
- 后续 PM/QA 会误以为 patch 已经 clean。

### 最小返修建议
- 去掉第 3-5 行尾随空格；
- 如果需要 Markdown 强制换行，请换成不会触发 whitespace check 的写法；
- 修完后重新补一条可复现的 check 证据。

## 其余部分我认可的点
除上面两项外，本轮交付其余方向基本正确：
1. 一句话版口径明确；
2. 工程 95 / 人工视觉 95 的边界写清楚了；
3. 科学、数学、语文、英语都被纳入口径边界；
4. final acceptance report 明确写了“非人工视觉 95”；
5. summary JSON 已加入：
   - `gate_passed_meaning`
   - `engineering_95_gate`
   - `human_visual_95_gate`
   - `public_claim_policy`
   - `subject_scope`
   - `sample_tier_policy`

所以这轮不是推翻重做，而是**两处最小口径返修**后即可快速回审。

## 非阻塞说明
- 当前任务目录没有 `verify.json`。
- 这不是本轮驳回的主因；主因是上面两个阻塞项。

## 建议
请 arch-1 先完成以下最小返修：
1. 统一 `public_claim_policy` / `claim_policy` 命名；
2. 清掉口径说明文档第 3-5 行 trailing whitespace，并补真实可复现的 check 证据。

修完后我可以按这两点做**快速复审**。
