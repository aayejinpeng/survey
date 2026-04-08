# Step 6: update.sh

## 状态

计划中，当前仓库里还没有 `update.sh`。

## 目标

通过一个轻量编排脚本，串联当前主链路：

1. `fetch_dblp.py`
2. `enrich_papers.py`
3. `score_papers.py`

用于做增量更新。

## 计划中的用法

```bash
bash update.sh
bash update.sh --topic cpu-ai
```

## 预期逻辑

1. Step 1 跳过已有 venue/year 文件，只抓新文件
2. Step 2 只补缺失 enrichment
3. Step 3 重算 topic score

## 当前替代方案

手工按下面顺序运行：

```bash
python3 fetch_dblp.py --config configs/venues.yaml --output-dir data/db/
python3 enrich_papers.py --input-dir data/db/ --output-dir data/enriched/
python3 score_papers.py --input-dir data/enriched/ --topic-config configs/topic-cpu-ai.yaml --output-dir data/topics/cpu-ai/
```
