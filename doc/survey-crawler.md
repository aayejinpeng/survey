# Survey Pipeline — 总览

这份文档保留 `survey-crawler` 这个名字，主要是为了兼容之前的入口习惯。

当前推荐使用的是模块化的 pipeline（详见 [README.md](../README.md)）：

1. `fetch_dblp.py`
2. `enrich_papers.py`
3. `score_papers.py`
4. `review_server.py` + `review.html`（Web 审阅）
5. `sync_zotero.py`（PDF 同步）
6. `build_graph.py`（计划中）

## 从哪里开始

- 文档入口：[README.md](README.md)
- Step 1：[step1-fetch-dblp.md](step1-fetch-dblp.md)
- Step 2：[step2-enrich-papers.md](step2-enrich-papers.md)
- Step 3：[step3-score-papers.md](step3-score-papers.md)
- Step 4：[step4-review.md](step4-review.md)
- Step 5：[step5-sync-zotero.md](step5-sync-zotero.md)
- Step 6：[step6-build-graph.md](step6-build-graph.md)

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
slice_csv.py → review_server.py（Web 审阅标记）
      ↓
sync_zotero.py（PDF 同步）
```

## 说明

- 旧版一体化 `survey_crawler.py` 已删除。
- 当前 Step 1-5 均已实现，Step 6（引用图）计划中。
