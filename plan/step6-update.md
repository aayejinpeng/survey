# Step 6: update.sh — 增量更新编排

## 目标

用 shell 脚本编排增量更新：只 fetch 新的 venue-year → 只 enrich 新增论文 → 重新 score。

不是 Python 脚本，而是一个编排脚本，串联 Step 1-3 的增量逻辑。

## 用法

```bash
# 增量更新：爬新年份，enrich 新论文，重新 score 所有 topic
bash update.sh

# 只更新特定 topic
bash update.sh --topic cpu-ai
```

## 逻辑

```bash
#!/bin/bash
# 1. Fetch new venue-years (已有的 --force 不设，自动跳过)
python3 fetch_dblp.py --config configs/venues.yaml --output-dir data/db/

# 2. Enrich only missing (默认行为，只补缺的)
python3 enrich_papers.py --input-dir data/db/ --output-dir data/enriched/

# 3. Re-score all topics
for topic_config in configs/topic-*.yaml; do
    topic_name=$(basename "$topic_config" .yaml | sed 's/topic-//')
    python3 score_papers.py \
        --input-dir data/enriched/ \
        --topic-config "$topic_config" \
        --output-dir "data/topics/$topic_name/"
done
```

## 增量原理

- **fetch_dblp**: `data/db/` 下已有文件自动跳过，只生成新的 `{venue}-{year}.csv`
- **enrich_papers**: `data/enriched/` 下已有文件检查每行的 abstract/citation_count，只补缺
- **score_papers**: 每次重跑（因为 enriched 数据可能更新，score 是纯计算很快）

## 增量 enrichment 的判断

`enrich_papers.py` 读取 `data/enriched/{venue}-{year}.csv`（如果存在）：
- 已有 abstract 且不是占位符 → 跳过
- `citation_count` > 0 → 跳过
- 否则 → 跑 S2/Crossref/arXiv

这意味着：
1. 首次：从 `data/db/` 复制到 `data/enriched/`，全部 enrich
2. 后续：只 enrich 新行或之前失败/缺失的行
3. 新 venue-year：从 `data/db/` 新文件 enrich
