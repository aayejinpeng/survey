# Step 5: build_graph.py

## 状态

计划中，当前仓库里还没有 `build_graph.py`。

## 目标

从 `filtered.csv` 构建引用图谱，并输出：

- `citation-graph.dot`
- `citation-graph.png`
- `citation-graph-stats.md`

## 计划中的用法

```bash
python3 build_graph.py \
    --input data/topics/cpu-ai/filtered.csv \
    --output-dir data/topics/cpu-ai/
```

## 预期输入列

- `paper_id`
- `title`
- `year`
- `doi`
- `s2_paper_id`
- `arxiv_id`
- `citation_count`
- `authors`

## 设计重点

1. 优先用 `s2_paper_id` 查引用关系
2. 缺 `s2_paper_id` 时，回退到 DOI 或 arXiv ID
3. 只在 filtered 集合内部建边
4. 缓存引用查询结果

## 当前替代方案

当前 Step 5 还未落地，先把 `scored.csv` 和人工筛选流程走顺，再推进图谱构建。
