# Survey Pipeline — Timeline（v3 模块化架构）

## 基线

- v1: 按 keyword 搜 S2/arXiv（已废弃）
- v2: 单文件 survey_crawler.py（耦合，已废弃）
- **v3: 模块化，每个 step 独立脚本，数据按目录分层**

## 架构

```
fetch_dblp.py → data/db/{venue}-{year}.csv
enrich_papers.py → data/enriched/{venue}-{year}.csv
score_papers.py + topic config → data/topics/{topic}/scored.csv
filter_papers.py → filtered.csv
build_graph.py → citation-graph.dot/.png/stats.md
```

## 排期

| Step | 脚本 | 依赖 | 状态 | 说明 |
|------|------|------|------|------|
| 1 | `fetch_dblp.py` | - | ✅ 已有 DBLP 解析逻辑 | 从 survey_crawler.py 拆出来 |
| 2 | `enrich_papers.py` | Step 1 | ✅ 已有 S2/Crossref/arXiv 逻辑 | 从 survey_crawler.py 拆出来 |
| 3 | `score_papers.py` | Step 2 | 🔄 新写 | 关键词打分，按 topic 解耦 |
| 4 | `filter_papers.py` | Step 3 | ⬜ | 轻量辅助 |
| 5 | `build_graph.py` | Step 4 | ✅ 已有 citation graph 逻辑 | 从 citation_graph.py 适配 |
| 6 | `update.sh` | Step 1-3 | ⬜ | 编排脚本 |

## 当前计划

1. 先把 survey_crawler.py 的 DBLP fetch 拆成 fetch_dblp.py
2. 把 enrichment 拆成 enrich_papers.py（支持单文件和目录模式）
3. 新写 score_papers.py（按 topic config 打分）
4. filter_papers.py（简单）
5. build_graph.py（适配新 CSV schema）
6. update.sh 编排

## 变更记录

| 日期 | 变更 |
|------|------|
| 2026-04-07 | v1 启动 |
| 2026-04-07 | v2 改为 DBLP venue-based |
| 2026-04-08 | v3 模块化拆分，6 个独立脚本 |
