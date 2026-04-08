# Step 3: score_papers.py

## 状态

已实现。

## 目标

从 `data/enriched/*.csv` 合并数据，按 topic 配置中的关键词打分，输出到 `data/topics/{topic}/scored.csv`。

## 常用命令

```bash
python3 score_papers.py \
    --input-dir data/enriched/ \
    --topic-config configs/topic-cpu-ai.yaml \
    --output-dir data/topics/cpu-ai/

python3 score_papers.py \
    --input data/enriched/isca-2024.csv data/enriched/micro-2024.csv \
    --topic-config configs/topic-cpu-ai.yaml \
    --output data/topics/cpu-ai/scored.csv

python3 score_papers.py \
    --input-dir data/enriched/ \
    --topic-config configs/topic-cpu-ai.yaml \
    --output-dir data/topics/cpu-ai/ \
    --min-relevance Medium
```

## 当前支持参数

| 参数 | 说明 |
|------|------|
| `--input-dir` | enriched 目录，与 `--input` 二选一 |
| `--input` | 一个或多个 enriched CSV |
| `--topic-config` | topic 配置 YAML |
| `--output-dir` | 输出目录，与 `--output` 二选一 |
| `--output` | 直接指定输出 CSV |
| `--min-relevance` | 只保留 `Low` / `Medium` / `High` 及以上 |

## 打分逻辑

- 评分文本：`title + abstract`
- 匹配方式：正则 + 单词边界，避免 `IME` 命中 `intermediate` 这类误伤
- 每个命中关键词按 `weight` 累加分数
- 输出：
  - `relevance_score`
  - `matched_keywords`
  - `relevance`

## 分档规则

- `High`: `score >= 5`
- `Medium`: `score >= 2`
- `Low`: `score >= 1`
- `None`: `score = 0`

## 输出

- `data/topics/{topic}/scored.csv`

当前 `configs/topic-cpu-ai.yaml` 对应：

- `data/topics/cpu-ai/scored.csv`

## Topic 配置

`configs/topic-*.yaml` 目前支持：

- `topic`
- `keywords`
- `filter_venues`
- `filter_years`

## 注意

- `--output-dir` 当前会直接写 `scored.csv`，不会再自动按 topic 名生成子路径
- 如果 topic config 里有重复关键词，分数会按出现次数重复累计
- 当前 `topic-cpu-ai.yaml` 的 `filter_venues` / `filter_years` 是注释状态，所以默认会对全部 enriched 数据评分
