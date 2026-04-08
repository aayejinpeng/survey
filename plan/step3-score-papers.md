# Step 3: score_papers.py — 关键词打分 + Topic 输出

## 目标

从 `data/enriched/*.csv` 读取 enriched 数据，按 topic 配置的关键词打分排序，输出到 `data/topics/{topic}/scored.csv`。

一个 enriched 数据集可以被多个 topic 使用，每个 topic 有自己的 keywords 和 filter。

## CLI

```bash
# 必须：指定 topic 配置
python3 score_papers.py \
    --input-dir data/enriched/ \
    --topic-config configs/topic-cpu-ai.yaml \
    --output-dir data/topics/cpu-ai/

# 指定输入文件（而不是整个目录）
python3 score_papers.py \
    --input data/enriched/isca-2024.csv data/enriched/micro-2024.csv \
    --topic-config configs/topic-cpu-ai.yaml \
    --output data/topics/cpu-ai/scored.csv

# 只输出 High/Medium 相关的
python3 score_papers.py \
    --input-dir data/enriched/ \
    --topic-config configs/topic-cpu-ai.yaml \
    --output-dir data/topics/cpu-ai/ \
    --min-relevance Medium
```

| 参数 | 说明 |
|------|------|
| `--input-dir` | enriched 目录（合并所有 CSV） |
| `--input` | 指定输入文件（可多个） |
| `--topic-config` | topic 配置文件 |
| `--output-dir` | 输出目录（自动创建 topic 子目录） |
| `--output` | 直接指定输出文件路径 |
| `--min-relevance` | 最低相关度：`Low`/`Medium`/`High`（默认全输出） |

## config: topic-cpu-ai.yaml

```yaml
topic: "CPU AI acceleration"

# 关键词 + 权重（可选，默认权重 1）
keywords:
  - term: "CPU"
    weight: 2
  - term: "tensor"
  - term: "matrix extension"
  - term: "AI inference"
  - term: "accelerator"
  - term: "AMX"
  - term: "SME"
  - term: "RISC-V"
    weight: 2
  - term: "IME"
  - term: "VME"
  - term: "MMA"
  - term: "RVV"
  - term: "vector"
  - term: "matmul"

# 可选：只包含特定 venue
filter_venues:
  - ISCA
  - MICRO
  - HPCA
  - ASPLOS
  - DAC
  - DATE

# 可选：年份范围
filter_years:
  start: 2023
  end: 2026
```

## 打分逻辑

```python
def score(paper, keywords):
    text = f"{paper['title']} {paper['abstract']}".lower()
    score = 0
    matched = []
    for kw in keywords:
        term = kw['term'].lower()
        weight = kw.get('weight', 1)
        if term in text:
            score += weight
            matched.append(kw['term'])
    return score, matched
```

## 输出 CSV: data/topics/{topic}/scored.csv

在 enriched 列基础上增加：

| 列 | 类型 | 说明 |
|---|---|---|
| `relevance_score` | int | 关键词匹配得分 |
| `matched_keywords` | string | 命中的关键词，逗号分隔 |
| `relevance` | string | `High`/`Medium`/`Low`/`None` |

Relevance 等级：
- `High`: score >= 5
- `Medium`: score >= 2
- `Low`: score >= 1
- `None`: score = 0（完全不相关）

按 relevance_score 降序排列。

## 行为

1. 读取所有输入 CSV，合并（按 paper_id 去重）
2. 应用 filter_venues 和 filter_years（如有）
3. 计算每篇论文的 score 和 matched_keywords
4. 按 score 降序排列
5. 输出到 `data/topics/{topic}/scored.csv`

## 输出示例

```
$ python3 score_papers.py \
    --input-dir data/enriched/ \
    --topic-config configs/topic-cpu-ai.yaml \
    --output-dir data/topics/cpu-ai/

Loaded: 332 papers from 4 files
After venue/year filter: 290 papers
Scoring with 14 keywords ...

Top papers:
  [score=8] TCP: A Tensor Contraction Processor for AI Workloads
  [score=7] AIO: An Abstraction for Performance Analysis...
  [score=6] ReAIM: A ReRAM-based Adaptive Ising Machine...

Distribution:
  High:   23 papers (score >= 5)
  Medium: 85 papers (score >= 2)
  Low:    112 papers (score = 1)
  None:   70 papers (score = 0)

Output: data/topics/cpu-ai/scored.csv (290 papers)
```
