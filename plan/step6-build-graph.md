# Step 6: build_graph.py — 引用图谱构建与可视化

## 状态

⬜ 计划中。

> **设计变更**：原计划 Step 6 为 `update.sh`（增量更新编排），但手动串联 Step 1-3 已足够使用。该位置现用于引用图谱构建。

## 目标

从已筛选的论文集合构建 citation graph，输出 DOT + PNG + 统计摘要。

## 计划 CLI

```bash
python3 build_graph.py \
    --input data/topics/cpu-ai/scored-score-gte11.csv \
    --output-dir data/topics/cpu-ai/

# 指定输出格式
python3 build_graph.py \
    --input data/topics/cpu-ai/scored-score-gte11.csv \
    --output-dir data/topics/cpu-ai/ \
    --format png,dot
```

| 参数 | 说明 |
|------|------|
| `--input` | scored/filtered CSV |
| `--output-dir` | 输出目录 |
| `--format` | `png`（默认）, `dot`, `pyvis` |

## 预期输入

CSV 中需要：`paper_id`, `title`, `year`, `doi`, `s2_paper_id`, `arxiv_id`, `citation_count`, `authors`

## 预期输出

| 文件 | 说明 |
|------|------|
| `citation-graph.dot` | Graphviz DOT |
| `citation-graph.png` | 静态图 |
| `citation-graph-stats.md` | 统计摘要 |

## 设计要点

1. 优先用 `s2_paper_id` 查 S2 references/citations
2. 无 `s2_paper_id` 时回退到 DOI 或 arXiv ID
3. 只在集合内部建边
4. 缓存到 `citation-cache.json`

## 增量更新（手动）

当不需要 build_graph 时，手动串联 Step 1-3 即可：

```bash
python3 fetch_dblp.py --config configs/venues.yaml --output-dir data/db/
python3 enrich_papers.py --input-dir data/db/ --output-dir data/enriched/
python3 score_papers.py --input-dir data/enriched/ --topic-config configs/topic-cpu-ai.yaml --output-dir data/topics/cpu-ai/
```
