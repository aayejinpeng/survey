# Step 5: build_graph.py — 引用图谱构建与可视化

## 目标

从 filtered.csv 构建 citation graph，输出 DOT + PNG + 统计摘要。

## CLI

```bash
python3 build_graph.py \
    --input data/topics/cpu-ai/filtered.csv \
    --output-dir data/topics/cpu-ai/

# 指定输出格式
python3 build_graph.py \
    --input data/topics/cpu-ai/filtered.csv \
    --output-dir data/topics/cpu-ai/ \
    --format png,dot

# 交互式 HTML（后续）
python3 build_graph.py \
    --input data/topics/cpu-ai/filtered.csv \
    --output-dir data/topics/cpu-ai/ \
    --format pyvis
```

| 参数 | 说明 |
|------|------|
| `--input` | filtered.csv（或 scored.csv，不要求一定 filter 过） |
| `--output-dir` | 输出目录 |
| `--format` | `png`（默认）, `dot`, `pyvis` |

## 输入

filtered.csv 的列中需要：`paper_id`, `title`, `year`, `doi`, `s2_paper_id`, `arxiv_id`, `citation_count`, `authors`

## 输出

| 文件 | 说明 |
|------|------|
| `citation-graph.dot` | Graphviz DOT（纯文本，可用在线工具渲染） |
| `citation-graph.png` | matplotlib 渲染的静态图 |
| `citation-graph-stats.md` | 统计摘要 |

## 图谱构建

1. 对 filtered 集合中的每篇论文：
   - 优先用 `s2_paper_id` 查 S2 references/citations 端点
   - 如无 `s2_paper_id` 但有 `doi` → `DOI:{doi}` 查 S2
   - 如无 `doi` 但有 `arxiv_id` → `ARXIV:{arxiv_id}` 查 S2
2. 只在 filtered 集合**内部**建边（A 引用了 B，B 也在 filtered 里）
3. 缓存到 `citation-cache.json`

## 可视化

- 节点大小：log(citation_count + 1)
- 节点颜色：按年份渐变（旧→蓝，新→红）
- 标签：截断标题 + 年份
- 布局：spring_layout（<30 节点）或 kamada_kawai_layout

## 统计摘要 citation-graph-stats.md

```markdown
# Citation Graph Statistics

Papers: {N}, Edges: {M}, Unresolved: {K}

## Most Influential (highest in-degree)
1. {Title} — cited by 8 papers in set
2. ...

## Most Connected (highest total degree)
...

## Clusters (weakly connected components)
- Cluster 1: 18 papers (main)
- Cluster 2: 3 papers (sub-topic)
...
```
