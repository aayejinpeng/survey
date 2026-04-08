# Survey Pipeline

`workspace/survey` 是一个面向体系结构 / 计算机系统论文调研的模块化流水线。当前主链路已经拆成独立脚本，输入输出清晰，适合按 venue/year 拉论文、做 enrichment，再按 topic 生成评分结果。

## 当前状态

| Step | 脚本 | 状态 | 输出 |
|------|------|------|------|
| 1 | `fetch_dblp.py` | 已实现 | `data/db/*.csv` |
| 2 | `enrich_papers.py` | 已实现 | `data/enriched/*.csv` |
| 3 | `score_papers.py` | 已实现 | `data/topics/{topic}/scored.csv` |
| 4 | `filter_papers.py` | 计划中 | `filtered.csv` |
| 5 | `build_graph.py` | 计划中 | `citation-graph.*` |
| 6 | `update.sh` | 计划中 | 增量编排 |

## 目录

```text
workspace/survey/
  fetch_dblp.py
  enrich_papers.py
  score_papers.py
  survey_crawler.py

  configs/
    venues.yaml
    topic-cpu-ai.yaml

  data/
    db/
    enriched/
    topics/

  doc/
    survey-crawler.md

  plan/
    README.md
    step1-fetch-dblp.md
    step2-enrich-papers.md
    step3-score-papers.md
    step4-filter.md
    step5-build-graph.md
    step6-update.md
```

## 快速开始

### 1. 拉取基础论文列表

```bash
python3 fetch_dblp.py --config configs/venues.yaml --output-dir data/db/
```

### 2. 补齐摘要和引用信息

```bash
python3 enrich_papers.py --input-dir data/db/ --output-dir data/enriched/
```

### 3. 按 topic 打分

```bash
python3 score_papers.py \
    --input-dir data/enriched/ \
    --topic-config configs/topic-cpu-ai.yaml \
    --output-dir data/topics/cpu-ai/
```

输出文件：

- `data/topics/cpu-ai/scored.csv`

## 数据流

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
```

## 配置文件

### `configs/venues.yaml`

定义全局 venue 列表和年份范围，供 Step 1 使用。

### `configs/topic-*.yaml`

定义 topic 名称、关键词和可选 filter，供 Step 3 使用。

当前示例：

- `configs/topic-cpu-ai.yaml`

## 重要说明

- 当前推荐入口是模块化三步：`fetch_dblp.py -> enrich_papers.py -> score_papers.py`
- `survey_crawler.py` 是早期一体化原型，不是当前主路径
- Step 4-6 还在 `plan/` 中定义，README 不把它们写成已实现功能
- `enrich_papers.py` 在没有 `SEMANTIC_SCHOLAR_API_KEY` 时会比较容易被 S2 限流

## 进一步阅读

- 用户手册：[doc/survey-crawler.md](/root/opencute/workspace/survey/doc/survey-crawler.md)
- 总体方案：[plan/README.md](/root/opencute/workspace/survey/plan/README.md)
- 时间线：[timeline.md](/root/opencute/workspace/survey/timeline.md)
