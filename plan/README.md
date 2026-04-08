# Survey Pipeline v3 — 模块化架构

## 核心思路

每个脚本独立运行，输入输出明确，数据按目录分层。一个 enriched 数据可服务多个 topic。

## 目录结构

```
workspace/survey/
  fetch_dblp.py          ← Step 1
  enrich_papers.py       ← Step 2
  score_papers.py        ← Step 3
  filter_papers.py       ← Step 4 (轻量辅助)
  build_graph.py         ← Step 5

  configs/               ← 用户配置
    venues.yaml          ← 所有要爬的 venue + year（全局）
    topic-cpu-ai.yaml    ← topic 配置（keywords, filter）
    topic-edge-ai.yaml

  data/
    db/                  ← Step 1 输出：raw DBLP，按 venue-year 分文件
      isca-2024.csv
      micro-2024.csv
      isca-2023.csv
      ...

    enriched/            ← Step 2 输出：enriched，同文件名
      isca-2024.csv      # + abstract, citation_count, s2_paper_id, arxiv_id
      ...

    topics/              ← Step 3 输出：按 topic 分目录
      cpu-ai/
        scored.csv       # enriched + relevance_score + matched_keywords
        filtered.csv     # keep=yes/maybe 的子集
        citation-graph.dot
        citation-graph.png
        citation-graph-stats.md
      edge-inference/
        scored.csv
        ...

  plan/                  ← 方案文档
  doc/                   ← 用户手册
  test_crawler.py        ← 测试
```

## 数据流

```
configs/venues.yaml
       ↓
  fetch_dblp.py
       ↓
  data/db/{venue}-{year}.csv
       ↓
  enrich_papers.py (S2 → Crossref → arXiv)
       ↓
  data/enriched/{venue}-{year}.csv
       ↓
  score_papers.py + configs/topic-xxx.yaml
       ↓
  data/topics/{topic}/scored.csv
       ↓
  filter_papers.py (人工在 spreadsheet 筛选)
       ↓
  data/topics/{topic}/filtered.csv
       ↓
  build_graph.py
       ↓
  citation-graph.dot + .png + -stats.md
```

## 每个脚本的 CLI 接口和 CSV Schema
