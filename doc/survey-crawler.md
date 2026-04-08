# Survey Pipeline — 总览

这份文档保留 `survey-crawler` 这个名字，主要是为了兼容之前的入口习惯。

当前推荐使用的不是旧版一体化 `survey_crawler.py`，而是模块化的 6-step pipeline：

1. `fetch_dblp.py`
2. `enrich_papers.py`
3. `score_papers.py`
4. `filter_papers.py`（计划中）
5. `build_graph.py`（计划中）
6. `update.sh`（计划中）

## 从哪里开始

- 文档入口：[README.md](README.md)
- Step 1：[step1-fetch-dblp.md](step1-fetch-dblp.md)
- Step 2：[step2-enrich-papers.md](step2-enrich-papers.md)
- Step 3：[step3-score-papers.md](step3-score-papers.md)
- Step 4：[step4-filter.md](step4-filter.md)
- Step 5：[step5-build-graph.md](step5-build-graph.md)
- Step 6：[step6-update.md](step6-update.md)

## 当前推荐工作流

```text
configs/venues.yaml
      ↓
fetch_dblp.py
      ↓
data/db/{venue}-{year}.csv
      ↓
enrich_papers.py
      ↓
data/enriched/{venue}-{year}.csv
      ↓
score_papers.py + configs/topic-*.yaml
      ↓
data/topics/{topic}/scored.csv
      ↓
人工筛选 keep/notes
      ↓
后续 Step 4 / Step 5
```

## 说明

- `survey_crawler.py` 仍在仓库里，但它代表的是旧方案，不是当前主维护路径。
- 当前真正已经可运行的主链路是 Step 1-3。
- Step 4-6 以 `plan/` 为准，文档里保留的是设计目标和预期接口。
