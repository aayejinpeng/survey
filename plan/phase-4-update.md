# Phase 4: 增量更新 Pipeline

## 目标

实现 `survey-update.md` skill，支持周更增量爬取，复用 Phase 1 的 `survey_crawler.py --mode update`。

## 文件

- `.claude/commands/survey/survey-update.md`

## 设计

### 核心逻辑

1. 读取 `crawl-state.json` → 获取 `last_incremental_crawl`（或 `last_full_crawl`）
2. 计算：
   - `last_crawl_date`
   - `overlap_days`（默认 7 天，来自 `config.yaml`）
   - `effective_start = last_crawl_date - overlap_days`
3. 运行 `survey_crawler.py --mode update`
   - arXiv：用 `effective_start` 构造 `submittedDate:[YYYYMMDD000000 TO 99999999999999]`
   - S2：先用粗粒度 `year` 过滤缩小范围，再在客户端按 `publicationDate` / `year` / `seen_paper_ids` 做二次过滤
4. 新论文 append 到已有 `abstracts.csv`
   - 只追加 net-new `paper_id`
   - 不覆盖已有 `keep` / `notes`
5. 报告：
   - `Found N new papers since {last_crawl_date}.`
   - `Effective search window started at {effective_start}.`
6. 提示用户筛选新行后运行 `/survey-filter` + `/survey-graph`

### 为什么需要 overlap window

- arXiv 的提交时间可精确到日期时间，S2 的搜索过滤更粗
- 如果严格从 `last_crawl_date` 起算，容易漏掉：
  - API 延迟入库的论文
  - 同一年内但晚于上次 crawl 的论文
- 因此 update 策略采用：
  - 拉宽查询窗口
  - 再用本地日期判断和 `seen_paper_ids` 去重收口

### Update vs Full 的区别

| 维度 | Full | Update |
|------|------|--------|
| 日期范围 | `config.yaml` 指定 | `last_crawl_date - overlap_days` → today |
| CSV 写入 | 刷新机器列并回填人工列 | 只追加 net-new 行 |
| 已有 keep/notes | 回填保留 | 严格保留 |
| 去重范围 | 本次结果内部 + 旧 CSV | 新结果 vs 旧 CSV + `seen_paper_ids` |
| 爬取量 | 大（可能数百篇） | 小（通常 10-30 篇/周） |

### survey-update.md Skill 格式

```
/survey-update "CPU AI acceleration"
/survey-update "RISC-V AI" — auto-graph
```

### 可选：自动图谱更新

如果用户传 `— auto-graph`：

1. 先 append 新论文到 `abstracts.csv`
2. 检查这些新论文是否都已经完成 `keep` 标记
3. 只有在以下条件满足时才自动重跑图谱：
   - `abstracts-filtered.csv` 已存在
   - 新追加论文没有空白 `keep`
4. 否则跳过自动出图，并明确提示用户先执行 `/survey-filter`

## crawl-state.json 状态管理

```json
{
  "topic_slug": "cpu-ai-acceleration",
  "last_full_crawl": "2026-04-07T14:30:00Z",
  "last_incremental_crawl": "2026-04-14T10:15:00Z",
  "seen_paper_ids": ["arxiv:2301.07041", "s2:abc123def456"],
  "crawl_history": [
    {
      "date": "2026-04-07",
      "mode": "full",
      "effective_start": "2023-01-01",
      "new_papers": 147
    },
    {
      "date": "2026-04-14",
      "mode": "update",
      "effective_start": "2026-04-07",
      "new_papers": 12
    }
  ]
}
```

## 验证

1. 先跑一次 full crawl，确认 `crawl-state.json` 正确生成。
2. 手动把 `last_crawl_date` 改到几天前，触发 overlap window。
3. 运行 `/survey-update "topic"`。
4. 检查：
   - CSV 只新增 net-new `paper_id`
   - 已有行未被修改
   - `crawl_history` 追加记录
5. 在同一状态下再次运行 `/survey-update "topic"`，确认第二次不会重复追加。

## 预估代码量

- `survey_crawler.py` 新增 update 模式逻辑：~80-120 行
- `survey-update.md`: ~60-80 行 markdown
