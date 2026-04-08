# Step 2: enrich_papers.py

## 状态

已实现，并且当前已经包含比早期方案更实用的 fallback 路径。

## 目标

读取 `data/db/*.csv`，补齐以下字段并输出到 `data/enriched/`：

- `abstract`
- `citation_count`
- `s2_paper_id`
- `arxiv_id`
- `categories`
- `published_date`

## 常用命令

```bash
python3 enrich_papers.py --input-dir data/db/ --output-dir data/enriched/
python3 enrich_papers.py --input data/db/isca-2024.csv --output data/enriched/isca-2024.csv
python3 enrich_papers.py --input-dir data/db/ --output-dir data/enriched/ --force
python3 enrich_papers.py --input-dir data/db/ --output-dir data/enriched/ --no-s2
python3 enrich_papers.py --input data/db/osdi-2025.csv --output data/enriched/osdi-2025.csv --limit 5
```

## 当前支持参数

| 参数 | 说明 |
|------|------|
| `--input-dir` | 输入目录，与 `--input` 二选一 |
| `--input` | 单个输入文件 |
| `--output-dir` | 输出目录，与 `--output` 二选一 |
| `--output` | 单个输出文件 |
| `--force` | 强制全部重跑 |
| `--no-s2` | 跳过 Semantic Scholar |
| `--no-crossref` | 跳过 Crossref |
| `--no-arxiv` | 跳过 arXiv |
| `--limit` | 只处理前 N 篇，适合调试 |

## 当前 enrichment 路径

### 1. S2 batch by DOI

对有 DOI 的论文，优先走批量接口。

### 2. S2 venue/year bulk candidate match

对无 DOI 的会议论文，先按 `venue + year` 拉候选池，再在本地按规范化标题精确匹配。

### 3. S2 title search fallback

对前一步没命中的论文，逐标题检索 S2，并做标题归一化匹配和年份校验。

### 4. Crossref fallback

对仍缺摘要、但有 DOI 的论文继续查 Crossref。

### 5. arXiv fallback

对仍缺摘要、且已有 `arxiv_id` 的论文查 arXiv。

### 6. 占位写回

如果所有来源都失败，则写：

- `[abstract unavailable]`
- 或 `[error: ...]`

## 默认处理策略

脚本默认只重试以下论文：

- `abstract` 为空
- `abstract` 为 `[abstract unavailable]`
- `abstract` 以 `[error:` 开头
- `citation_count` 为 `0` 或空

已完成的数据会自动跳过。

## 输出

- `data/enriched/{venue}-{year}.csv`

在 Step 1 基础上新增：

- `arxiv_id`
- `s2_paper_id`
- `abstract`
- `source`
- `categories`
- `citation_count`
- `published_date`
- `crawled_date`
- `keep`
- `notes`

## 实际注意事项

- 没有 `SEMANTIC_SCHOLAR_API_KEY` 时，S2 很容易 429，整批运行会变慢
- 对纯 title 的数据集，S2 仍然可能是主要瓶颈
- 输出时会保留已有 `keep` / `notes`
- 当前日志会明确打印各阶段统计，但不会额外写日志文件
