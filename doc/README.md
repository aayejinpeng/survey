# Survey Docs

`workspace/survey/doc/` 保存面向使用者的文档入口。

当前 pipeline 已经从早期一体化 `survey_crawler.py`，切换为按步骤拆分的模块化流程：

1. `fetch_dblp.py`
2. `enrich_papers.py`
3. `score_papers.py`
4. `filter_papers.py`（计划中）
5. `build_graph.py`（计划中）
6. `update.sh`（计划中）

## 当前状态

| Step | 文档 | 脚本状态 | 说明 |
|------|------|----------|------|
| 1 | [step1-fetch-dblp.md](step1-fetch-dblp.md) | 已实现 | 抓 DBLP venue/year 论文列表 |
| 2 | [step2-enrich-papers.md](step2-enrich-papers.md) | 已实现 | 补摘要、引用数、S2/arXiv 标识 |
| 3 | [step3-score-papers.md](step3-score-papers.md) | 已实现 | 按 topic 配置关键词打分 |
| 4 | [step4-filter.md](step4-filter.md) | 计划中 | 从 `scored.csv` 提取人工筛选结果 |
| 5 | [step5-build-graph.md](step5-build-graph.md) | 计划中 | 生成引用图谱与统计摘要 |
| 6 | [step6-update.md](step6-update.md) | 计划中 | 增量更新编排 |

## 推荐阅读顺序

1. 先看 [survey-crawler.md](survey-crawler.md) 了解整体工作流
2. 再看 Step 1-3 文档，按顺序执行当前可落地的主链路
3. 如果要继续推进后续功能，再看 Step 4-6 文档

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

## 关键目录

| 路径 | 用途 |
|------|------|
| `configs/venues.yaml` | Step 1 的全局 venue 配置 |
| `configs/topic-*.yaml` | Step 3 的 topic 配置 |
| `data/db/` | Step 1 输出 |
| `data/enriched/` | Step 2 输出 |
| `data/topics/{topic}/` | Step 3 及后续 topic 结果 |
| `plan/` | 方案与时间线 |

## 说明

- 当前文档会优先反映“脚本实际可运行的行为”，不把计划中的 Step 4-6 写成已实现。
- `survey_crawler.py` 仍保留在仓库中，但不是当前推荐入口。
