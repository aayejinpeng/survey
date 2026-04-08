# Step 1: fetch_dblp.py — DBLP Proceedings 爬取

## 目标

从 DBLP 抓取指定 venue×year 的论文列表，输出到 `data/db/` 目录，每对 venue-year 一个 CSV。

## CLI

```bash
python3 fetch_dblp.py --config configs/venues.yaml --output-dir data/db/
python3 fetch_dblp.py --config configs/venues.yaml --output-dir data/db/ --venues ISCA MICRO
python3 fetch_dblp.py --config configs/venues.yaml --output-dir data/db/ --years 2024
```

| 参数 | 必需 | 说明 |
|------|------|------|
| `--config` | 是 | venues.yaml 路径 |
| `--output-dir` | 是 | 输出目录（`data/db/`） |
| `--venues` | 否 | 只跑指定 venue（逗号分隔），默认全部 |
| `--years` | 否 | 只跑指定年份（逗号分隔），默认 config 里的 date_range |
| `--force` | 否 | 覆盖已有文件（默认跳过） |

## config: venues.yaml

```yaml
venues:
  - id: ISCA
    dblp_key: conf/isca
  - id: MICRO
    dblp_key: conf/micro
  - id: HPCA
    dblp_key: conf/hpca
  - id: ASPLOS
    dblp_key: conf/asplos
  - id: DAC
    dblp_key: conf/dac
  - id: DATE
    dblp_key: conf/date

date_range:
  start: 2023
  end: 2026
```

## 输出 CSV: data/db/{venue}-{year}.csv

| 列 | 类型 | 说明 |
|---|---|---|
| `paper_id` | string | `doi:{doi}` 或 `dblp:{dblp_rec_id}` |
| `title` | string | 论文标题 |
| `authors` | string | 作者，分号分隔 |
| `year` | int | 发表年份 |
| `venue` | string | 会议/期刊 ID（来自 config） |
| `doi` | string | DOI（如有） |
| `url` | string | DOI 链接或 DBLP 链接 |
| `dblp_id` | string | DBLP record ID（如 `conf/isca/Author24`） |

## 行为

1. 遍历 venues × years
2. 对每个 venue-year：构造 URL `https://dblp.org/db/{dblp_key}/{abbr}{year}`
3. 请求 HTML，429/5xx 指数退避重试（最多 3 次，最长等 30s）
4. 404 直接跳过（proceedings 不存在）
5. 解析 `<li class="entry inproceedings">` → COinS → title, authors, DOI
6. 按 DOI 去重（同 venue-year 内）
7. 写入 `data/db/{venue}-{year}.csv`
8. 如果文件已存在且非 `--force`，跳过

## 输出示例

```
$ python3 fetch_dblp.py --config configs/venues.yaml --output-dir data/db/

Fetching ISCA 2023 ... 58 papers
Fetching ISCA 2024 ... 87 papers
Fetching ISCA 2025 ... SKIP (404, proceedings not found)
Fetching MICRO 2023 ... 72 papers
Fetching MICRO 2024 ... 115 papers

Done: 332 papers from 4 venue×year
  data/db/isca-2023.csv  (58)
  data/db/isca-2024.csv  (87)
  data/db/micro-2023.csv  (72)
  data/db/micro-2024.csv  (115)
  Skipped: ISCA 2025 (404)
```

## 增量更新

后续只加新的 venue-year 到 config，跑 `--venues NEW --years 2025`，已有文件不重跑。
