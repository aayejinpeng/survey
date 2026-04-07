# Phase 4: 增量更新 Pipeline

## 目标

实现 `survey-update.md` skill，支持周更增量爬取，复用 Phase 1 的 `survey_crawler.py --mode update`。

## 文件

- `.claude/commands/survey/survey-update.md`

## 设计

### 核心逻辑

1. 读取 `crawl-state.json` → 获取 `last_incremental_crawl`（或 `last_full_crawl`）
2. 计算日期范围：`last_crawl_date` → 今天
3. 运行 `survey_crawler.py --mode update`
   - 只爬取 last_crawl_date 之后的新论文
   - arXiv：`submittedDate:[YYYYMMDD000000 TO 99999999999999]`
   - S2：`year` 参数范围过滤
4. 新论文 append 到已有 abstracts.csv（不覆盖已有 keep/notes 列）
5. 报告：`Found N new papers since {date}. Added to CSV.`
6. 提示用户筛选新行后运行 `/survey-filter` + `/survey-graph`

### Update vs Full 的区别

| 维度 | Full | Update |
|------|------|--------|
| 日期范围 | config.yaml 指定 | last_crawl_date → today |
| CSV 写入 | 覆盖 | Append（保留已有行）|
| 已有 keep/notes | 不存在 | 严格保留 |
| 去重范围 | 所有新结果之间 | 新结果 vs seen_paper_ids |
| 爬取量 | 大（可能数百篇） | 小（通常 10-30 篇/周）|

### survey-update.md Skill 格式

```
/survey-update "CPU AI acceleration"
/survey-update "RISC-V AI" — auto-graph    ← 筛选后自动重跑图谱
```

### 可选：自动图谱更新

如果用户传 `— auto-graph`，在 append 新论文后：
1. 自动对 keep=yes 的论文重跑 citation_graph.py
2. 生成更新后的图谱（包含新论文与已有论文的引用关系）

## crawl-state.json 状态管理

```json
{
  "topic_slug": "cpu-ai-acceleration",
  "last_full_crawl": "2026-04-07T14:30:00Z",
  "last_incremental_crawl": "2026-04-14T10:15:00Z",
  "seen_paper_ids": ["2301.07041", "abc123def456", ...],
  "crawl_history": [
    {"date": "2026-04-07", "mode": "full", "new_papers": 147},
    {"date": "2026-04-14", "mode": "update", "new_papers": 12}
  ]
}
```

## 验证

1. 先跑一次 full crawl，确认 crawl-state.json 正确生成
2. 等几天（或手动修改 last_crawl_date 为几天前）
3. 运行 `/survey-update "topic"`
4. 检查 CSV 是否只新增了论文，已有行未被修改
5. 检查 crawl_history 是否追加了记录

## 预估代码量

- survey_crawler.py 新增 update 模式逻辑：~50-80 行（复用已有函数）
- survey-update.md: ~60 行 markdown
