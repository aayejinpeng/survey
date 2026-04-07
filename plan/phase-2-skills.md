# Phase 2: Claude Code Skills — crawl/filter skill

## 目标

创建 `survey-crawl.md` 和 `survey-filter.md` 两个 skill，串联 Phase 1 的爬取脚本和人工筛选流程。

## 文件

- `.claude/commands/survey/survey-crawl.md`
- `.claude/commands/survey/survey-filter.md`

## survey-crawl.md 设计

### 功能
1. 解析用户参数（topic, year range, venues）
2. 创建 `.claude/survey-data/{topic-slug}/` 目录
3. 生成 `config.yaml`（基于用户参数 + 合理默认值）
4. 运行 `survey_crawler.py --mode full`
5. 报告结果，提示用户编辑 CSV

### 参数格式
```
/survey-crawl "CPU AI acceleration"
/survey-crawl "RISC-V AI accelerator" — year: 2024-2026
/survey-crawl "AMX tensor unit" — sources: arxiv
```

### 关键逻辑
- topic-slug 生成：lowercase + 空格→连字符 + 只保留字母数字
- 如果已有 config.yaml，问用户是覆盖还是复用
- 运行后统计：N papers from arXiv, M from S2, K unique
- 提示：`Open {csv_path} in a spreadsheet, set keep column to yes/no/maybe, then run /survey-filter "{topic}"`

## survey-filter.md 设计

### 功能
1. 读取 `abstracts.csv`
2. 检查哪些行有 keep 值
3. 提取 keep=yes 和 keep=maybe 的行 → `abstracts-filtered.csv`
4. 报告统计

### 关键逻辑
- 如果没有任何行设置了 keep，提示用户先去编辑
- 输出统计：N total, M selected (yes: X, maybe: Y, no: Z, empty: W)
- 完成后提示：`Run /survey-graph "{topic}" to generate the citation graph`

## 验证

1. 运行 `/survey-crawl "test topic"`，检查 config.yaml 生成正确
2. 手动在 CSV 中设置几行 keep=yes
3. 运行 `/survey-filter "test topic"`，检查 filtered.csv 只包含选中的行

## 预估代码量

- survey-crawl.md: ~80 行 markdown
- survey-filter.md: ~40 行 markdown
