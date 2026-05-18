# 任务：归档横评样例到 artifacts 目录

## 任务类型
development（数据整理）

## 目标
将所有横评评测数据统一归档整理到 artifacts/pdf2word/ 目录，方便后续查阅和对比。

## 任务边界
- 只做数据整理和归档，不跑模型
- 整理已有评测产物
- 不修改代码

## 输入事实
- 所有评测数据在 /Users/linsuchang/Desktop/work/chiralium/artifacts/pdf2word/model-eval/ 下
- 横评报告在 /Users/linsuchang/Desktop/work/chiralium/design/pdf2word/ 下
- 部分手动整理的 DOCX 在 example/扫描件 /docx横评对比/

## 约束
- write_scope 以 task.json 为准
- 用 cp 而非 mv，保留原始数据
- 不修改任何原始数据文件
- PaddleOCR-VL 缺数学试卷需在 README 注明

## 当前数据分布
所有数据在 /Users/linsuchang/Desktop/work/chiralium/ 下：

- artifacts/pdf2word/model-eval/20260514-144102/ (apple_baseline)
- artifacts/pdf2word/model-eval/20260514-170529/ (mineru_lite)
- artifacts/pdf2word/model-eval/20260515-090642/ (mineru_full)
- artifacts/pdf2word/model-eval/20260515-090816/ (glm_ocr)
- artifacts/pdf2word/model-eval/20260515-112748/ (paddleocr_vl)
- artifacts/pdf2word/model-eval/20260515-124038/ (qwen3_vl_8b)
- example/扫描件 /docx横评对比/ (部分手动整理的 DOCX)

## 归档要求

### 1. 统一目录结构
```
artifacts/pdf2word/final-archive/
├── profiles/
│   ├── apple_baseline/
│   │   ├── 五下科学/
│   │   │   ├── output.docx
│   │   │   ├── metrics.json
│   │   │   └── pages.jsonl
│   │   ├── 数学八年级/
│   │   ├── 数学试卷/
│   │   ├── 英语八年级/
│   │   └── 语文五年级/
│   ├── mineru_lite/
│   ├── mineru_full/
│   ├── glm_ocr/
│   ├── paddleocr_vl/
│   ├── qwen3_vl_8b/
│   └── glm_46v_flash/ (空，标注 blocked)
├── reports/
│   ├── 横评最终报告.md
│   ├── 候选增强可行性报告.md
│   ├── hybrid管线设计.md
│   └── 各 profile comparison_report.json
└── README.md (归档说明)
```

### 2. 归档内容
- 每个 profile 的 5 样例产物（output.docx、metrics.json、pages.jsonl、warnings.json）
- 各 profile 的 comparison_report.json（如有）
- 横评最终报告、候选报告、hybrid 设计文档
- README.md 说明归档内容和数据来源

### 3. 样例命名统一
- 五下科学
- 数学八年级
- 数学试卷
- 英语八年级
- 语文五年级


## 交付物
1. 归档目录结构完整
2. README.md 归档说明
3. result.json 列出归档统计

## 验收标准
1. 6 个 profile 的数据均已归档
2. 目录结构一致
3. 报告文档已收录
4. README 有完整说明

## 下游动作
归档后可推送摘要给林总工，后续 GLM-4.6V 数据补入。
