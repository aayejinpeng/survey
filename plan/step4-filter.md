# Step 4: filter_papers.py — 提取用户筛选结果

## 目标

从 scored.csv 提取 `keep=yes` 和 `keep=maybe` 的论文，输出 filtered.csv。

这是一个轻量辅助脚本。用户也可以直接在 spreadsheet 里操作 CSV，不用这个脚本。

## CLI

```bash
python3 filter_papers.py \
    --input data/topics/cpu-ai/scored.csv \
    --output data/topics/cpu-ai/filtered.csv

# 只保留 High/Medium 相关度的
python3 filter_papers.py \
    --input data/topics/cpu-ai/scored.csv \
    --output data/topics/cpu-ai/filtered.csv \
    --min-relevance Medium

# 不要求 keep 列，直接按相关度截取 top N
python3 filter_papers.py \
    --input data/topics/cpu-ai/scored.csv \
    --output data/topics/cpu-ai/filtered.csv \
    --top 30
```

| 参数 | 说明 |
|------|------|
| `--input` | scored.csv |
| `--output` | filtered.csv |
| `--min-relevance` | 最低相关度筛选 |
| `--top` | 按 score 截取 top N（不依赖 keep 列） |

## 行为

1. 读取 scored.csv
2. 按 `keep` 列筛选（`yes` / `maybe`），或按 `--top` 截取
3. 可叠加 `--min-relevance`
4. 输出 filtered.csv（列与 scored.csv 相同）

## 用户工作流

```
scored.csv → 在 spreadsheet 里浏览，设 keep 列 → filter_papers.py → filtered.csv → build_graph.py
         或
scored.csv → filter_papers.py --top 30 → filtered.csv → build_graph.py
```
