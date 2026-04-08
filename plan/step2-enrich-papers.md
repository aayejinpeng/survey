# Step 2: enrich_papers.py — S2/Crossref/arXiv Enrichment

## 目标

读取 `data/db/*.csv`（或指定的文件），通过 S2 → Crossref → arXiv 补充 abstract、citation_count 等字段，输出到 `data/enriched/`。

## CLI

```bash
# 默认：处理 data/db/ 下所有 CSV，只补缺失项
python3 enrich_papers.py --input-dir data/db/ --output-dir data/enriched/

# 只处理指定文件
python3 enrich_papers.py --input data/db/isca-2024.csv --output data/enriched/isca-2024.csv

# 强制全部重跑（包括已有 abstract 的）
python3 enrich_papers.py --input-dir data/db/ --output-dir data/enriched/ --force

# 跳过 S2（只做 Crossref + arXiv）
python3 enrich_papers.py --input-dir data/db/ --output-dir data/enriched/ --no-s2

# 只处理缺失的（默认行为，可省略）
python3 enrich_papers.py --input-dir data/db/ --output-dir data/enriched/ --only-missing
```

| 参数 | 说明 |
|------|------|
| `--input-dir` | 输入目录（与 `--input` 二选一） |
| `--input` | 单个输入文件 |
| `--output-dir` | 输出目录（与 `--output` 二选一） |
| `--output` | 单个输出文件 |
| `--force` | 全部重跑（默认只补缺失项） |
| `--only-missing` | 只处理 abstract 为空/[abstract unavailable]/[error:...] 的行（默认） |
| `--no-s2` | 跳过 S2 enrichment |
| `--no-crossref` | 跳过 Crossref fallback |
| `--no-arxiv` | 跳过 arXiv fallback |

## 输入 CSV（来自 Step 1）

`data/db/{venue}-{year}.csv` 的列：paper_id, title, authors, year, venue, doi, url, dblp_id

## 输出 CSV: data/enriched/{venue}-{year}.csv

在 Step 1 的列基础上增加：

| 列 | 类型 | 说明 |
|---|---|---|
| `abstract` | string | 摘要（真实内容 / `[error:...]` / `[abstract unavailable]`） |
| `citation_count` | int | S2 引用数 |
| `s2_paper_id` | string | S2 paperId |
| `arxiv_id` | string | arXiv ID（从 S2 externalIds 获取） |
| `categories` | string | S2 fieldsOfStudy，分号分隔 |
| `published_date` | string | YYYY-MM-DD（S2 补充的精确日期） |
| `source` | string | `dblp` |

## Enrichment 流程（每篇论文）

```
有 DOI？
  ├─ 是 → S2 get_paper(DOI:{doi})
  │       ├─ 成功 → 写入 citation_count, s2_paper_id, abstract(如有), arxiv_id(如有)
  │       └─ 429 → 指数退避 2→4→8s，超过 30s 放弃，abstract 写入 [error: 429 ...]
  └─ 否 → 跳过 S2

abstract 仍为空或占位符？
  ├─ 是 + 有 DOI → Crossref API
  │       ├─ 有 abstract → 写入
  │       └─ 429 → 指数退避，放弃则 abstract = [error: 429 ...]
  ├─ 是 + 有 arxiv_id → arXiv API
  │       ├─ 有 abstract → 写入
  │       └─ 429 → 指数退避，放弃则 abstract = [error: 429 ...]
  └─ 是 + 都没有 → abstract = [abstract unavailable]
```

## 判断"需要 enrich"的条件

```python
def needs_enrichment(paper):
    ab = paper.get("abstract", "")
    if not ab: return True
    if ab == "[abstract unavailable]": return True
    if ab.startswith("[error:"): return True
    cc = paper.get("citation_count", "")
    if cc in ("0", ""): return True
    return False
```

## 合并写回逻辑

1. 读取输入 CSV
2. 筛选需要 enrich 的行（或 `--force` 全部）
3. 跑 enrichment
4. 合并回所有行（已完成的行不动）
5. 原子写入输出 CSV（.tmp → rename）
6. 保留 `keep`/`notes` 列（如有）

## 输出示例

```
$ python3 enrich_papers.py --input-dir data/db/ --output-dir data/enriched/

Processing isca-2024.csv (87 papers)
  Need enrichment: 87 (skipped: 0 already complete)
  [1/87] S2 OK  (enriched: 1, abstracts: 1, failed: 0)
  [10/87] S2 OK  (enriched: 10, abstracts: 6, failed: 0)
  ...
  Phase B result: 80 enriched, 60 abstracts from S2
  Phase C: 27 missing → Crossref=8, arXiv=12, unavailable=7
  Written: data/enriched/isca-2024.csv

Processing micro-2024.csv (115 papers)
  ...

Summary:
  isca-2024: 80/87 S2 OK, 60+8+12=80 abstracts available, 7 unavailable
  micro-2024: 95/115 S2 OK, 75+10+8=93 abstracts available, 22 unavailable
```
