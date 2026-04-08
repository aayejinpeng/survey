# Survey Crawler — 用户手册

## 概览

`survey_crawler.py` 是一个 venue-based 文献调研工具，按用户指定的会议/期刊 + 年份范围从 DBLP 获取论文，再通过多个 API 补充元数据，最终输出结构化 CSV 供人工筛选。

## 两个子命令

| 命令 | 功能 | 适用场景 |
|------|------|----------|
| `crawl` | DBLP fetch + enrichment | 首次获取或增量更新 |
| `enrich` | 只做 enrichment，不爬 DBLP | 已有 CSV 需要补全 abstract/citation |

## Pipeline 四个阶段

```
config.yaml
    ↓
┌─────────────────────────────────────────────────────┐
│ Phase A: DBLP Fetch                                 │
│   指定 venue × year → 抓取 DBLP proceedings 页面    │
│   提取: title, authors, DOI, venue, year             │
│   输出: 论文列表 (无 abstract, 无 citation_count)    │
│   429/5xx 自动重试 (指数退避, 最多 3 次)             │
│   404 跳过 (proceedings 不存在)                      │
├─────────────────────────────────────────────────────┤
│ Phase B: S2 Enrichment                              │
│   用 DOI 查 Semantic Scholar                        │
│   补充: citation_count, abstract, s2_paper_id,      │
│         arxiv_id, fieldsOfStudy                     │
│   429 自动重试 (指数退避 2→4→8s, 超 30s 放弃)      │
│   失败时写入错误标注到 abstract 列                   │
├─────────────────────────────────────────────────────┤
│ Phase C: Abstract Fallback                          │
│   对仍缺失 abstract 的论文，按优先级补全:           │
│   1. Crossref API (via DOI)                         │
│   2. arXiv API (via arxiv_id)                       │
│   3. 标记 [abstract unavailable]                    │
│   同样支持 429 重试 + 错误标注                      │
├─────────────────────────────────────────────────────┤
│ Phase D: Score + Write                              │
│   关键词相关性打分 + 排序                            │
│   merge-safe CSV 写入 (保留人工 keep/notes 列)      │
│   状态文件更新                                       │
└─────────────────────────────────────────────────────┘
    ↓
abstracts.csv  →  用户在 spreadsheet 中筛选  →  /survey-filter  →  /survey-graph
```

## Phase A: DBLP Fetch

**功能**：从 DBLP 会议 proceedings HTML 页面提取论文列表。

**数据源**：`https://dblp.org/db/{dblp_key}/{abbreviation}{year}`
- 例：ISCA 2024 → `https://dblp.org/db/conf/isca/isca2024`
- MICRO 2023 → `https://dblp.org/db/conf/micro/micro2023`

**解析策略**：
1. 按 `<li class="entry inproceedings" id="...">` 定位论文边界
2. 从 `<a href="https://doi.org/...">` 提取 DOI
3. 从相邻 COinS `<span class="Z3988">` 的 `rft.atitle` 和 `rft.au` 提取标题和作者
4. 只保留 `inproceedings` 类型（过滤掉 editorial、preface 等）

**输出字段**：`paper_id`, `title`, `authors`, `year`, `venue`, `doi`, `url`（无 abstract）

**重试机制**：
- 429 / 502 / 503 / 504：指数退避重试最多 2 次（2s → 4s）
- 404：直接跳过（proceedings 不存在），输出 `SKIP (404, proceedings not found)`
- 其他错误：标记 FAILED，记录到 `fetch_failures` 列表

**失败报告**：所有失败的 venue×year 会在 Phase A 结束后汇总输出：
```
  WARNING: 2 venue×year fetches FAILED:
    - ISCA 2023: fetch failed
    - HPCA 2025: fetch failed
```

---

## Phase B: S2 Enrichment

**功能**：用 DOI 逐篇查 Semantic Scholar，补充引用数和摘要。

**数据源**：Semantic Scholar `get_paper` API
- 输入：`DOI:{doi}`
- 补充字段：`citation_count`, `abstract`, `s2_paper_id`, `arxiv_id`（从 externalIds）, `fieldsOfStudy`

**429 重试机制**：
- 指数退避：2s → 4s → 8s（每次翻倍）
- 超过 30s 等待就放弃
- 放弃后在 abstract 列写入：`[error: 429 rate-limited after 3 retries, please fetch manually]`

**其他错误标注**：
- HTTP 非 429 错误：`[error: HTTP {code}, please fetch manually]`
- 网络错误：`[error: {具体错误}, please fetch manually]`

**rate limit**：
- 无 API key：~1 req/s
- 有 API key（环境变量 `SEMANTIC_SCHOLAR_API_KEY`）：更高限额
- 脚本默认 1.1s 间隔

**跳过方式**：`--no-s2` 或 `--no-enrich`

---

## Phase C: Abstract Fallback

**功能**：对 Phase B 后仍缺失 abstract 的论文，尝试其他来源补全。

**Fallback 链**：
1. **Crossref API**（via DOI）：大多数 IEEE/ACM/Springer 论文可获取
   - 免费无需 key
   - 同样支持 429 指数退避重试
2. **arXiv API**（via arxiv_id）：有预印本的论文
   - 需要 Phase B 先从 S2 获取到 arxiv_id
   - 同样支持 429 指数退避重试
3. **标记**：
   - 成功：写入摘要内容
   - 429 重试耗尽：`[error: 429 rate-limited after 3 retries, please fetch manually]`
   - 其他错误：`[error: HTTP {code}, please fetch manually]`
   - 所有来源都没有摘要：`[abstract unavailable]`

**跳过方式**：`--no-enrich` 跳过整个 Phase C

---

## Phase D: Score + Write

**功能**：关键词打分排序 + merge-safe CSV 写入 + 状态更新。

**关键词打分**：
- 对 title + abstract 做简单关键词匹配计数
- 按得分降序排列（不影响内容，只影响默认顺序）

**merge-safe 写入**：
- `full` 模式：刷新所有机器列，但按 `paper_id` 回填已有的 `keep`/`notes` 列
- `update` 模式：只追加 net-new 的 `paper_id`，已有行完全不改动
- 原子写入：先写 `.tmp` 再 `os.replace`

**状态文件**（`crawl-state.json`）：
- `seen_paper_ids`：所有已见过的 paper_id 集合
- `crawled_venues`：每个 venue×year 的爬取记录
- `crawl_history`：每次 crawl 的日期/模式/论文数

---

## `crawl` 命令

从 DBLP 获取论文 + enrichment，输出 CSV。

```bash
# 完整 crawl（所有阶段）
python3 survey_crawler.py crawl \
    --config config.yaml \
    --output abstracts.csv \
    --state crawl-state.json \
    --mode full

# 只获取 DBLP 列表，不做 enrichment（快速）
python3 survey_crawler.py crawl \
    --config config.yaml \
    --output abstracts.csv \
    --state crawl-state.json \
    --mode full \
    --no-enrich

# 增量更新（只爬新年度 proceedings）
python3 survey_crawler.py crawl \
    --config config.yaml \
    --output abstracts.csv \
    --state crawl-state.json \
    --mode update

# 跳过 S2（只做 Crossref + arXiv fallback）
python3 survey_crawler.py crawl \
    --config config.yaml \
    --output abstracts.csv \
    --state crawl-state.json \
    --mode full \
    --no-s2
```

### 参数

| 参数 | 必需 | 说明 |
|------|------|------|
| `--config` | 是 | config.yaml 路径 |
| `--output` | 是 | 输出 CSV 路径 |
| `--state` | 是 | 状态 JSON 路径 |
| `--mode` | 否 | `full`（默认）或 `update` |
| `--no-enrich` | 否 | 跳过所有 enrichment |
| `--no-s2` | 否 | 跳过 S2，只做 Crossref + arXiv |

---

## `enrich` 命令

对已有 CSV 做 enrichment，**不爬 DBLP**。

**默认行为**：只处理需要 enrichment 的论文（空 abstract、`[error:...]`、`[abstract unavailable]`、citation_count 为 0）。已完成的论文自动跳过。

```bash
# 默认：只补全缺失/错误的论文
python3 survey_crawler.py enrich \
    --input abstracts.csv \
    --output abstracts.csv \
    --state crawl-state.json

# 强制全部重跑
python3 survey_crawler.py enrich \
    --input abstracts.csv \
    --output abstracts.csv \
    --state crawl-state.json \
    --force

# 跳过 S2（只做 Crossref + arXiv）
python3 survey_crawler.py enrich \
    --input abstracts.csv \
    --output abstracts.csv \
    --state crawl-state.json \
    --no-s2
```

### 参数

| 参数 | 必需 | 说明 |
|------|------|------|
| `--input` | 是 | 输入 CSV 路径 |
| `--output` | 是 | 输出 CSV 路径（可与 input 相同） |
| `--state` | 是 | 状态 JSON 路径 |
| `--no-s2` | 否 | 跳过 S2 enrichment |
| `--force` | 否 | 强制全部重跑（默认只补缺失项） |

### 判断哪些论文需要 enrichment

```python
def _needs_enrichment(paper):
    abstract = paper["abstract"]
    if not abstract:                          # 空摘要
        return True
    if abstract.startswith("[error:"):        # 之前 429/网络错误
        return True
    if abstract == "[abstract unavailable]":  # 所有来源都没找到
        return True
    if citation_count == 0 or empty:          # 没有引用数
        return True
    return False
```

---

## config.yaml 格式

```yaml
topic: "你的调研主题"

venues:
  - id: ISCA           # 显示名称
    type: conference
    dblp_key: conf/isca  # DBLP URL 路径
  - id: MICRO
    type: conference
    dblp_key: conf/micro
  - id: HPCA
    type: conference
    dblp_key: conf/hpca
  - id: ASPLOS
    type: conference
    dblp_key: conf/asplos
  - id: DAC
    type: conference
    dblp_key: conf/dac
  - id: DATE
    type: conference
    dblp_key: conf/date

date_range:
  start: 2023
  end: 2026

enrichment:
  s2:
    enabled: true
  crossref:
    enabled: true
  arxiv:
    enabled: true

keywords: ["CPU", "tensor", "AI", "accelerator", "RISC-V"]

update:
  overlap_years: 1
```

### 常见 DBLP venue key

| Venue | dblp_key | 类型 |
|-------|----------|------|
| ISCA | conf/isca | conference |
| MICRO | conf/micro | conference |
| HPCA | conf/hpca | conference |
| ASPLOS | conf/asplos | conference |
| DAC | conf/dac | conference |
| DATE | conf/date | conference |
| ISSCC | conf/isscc | conference |
| OSDI | conf/osdi | conference |
| SOSP | conf/sosp | conference |
| ATC | conf/usenix | conference |
| MLSys | conf/mlsys | conference |
| NeurIPS | conf/nips | conference |
| IEEE TPAMI | journals/pami | journal |
| IEEE JSAC | journals/jsac | journal |

---

## CSV 中的错误标注

enrichment 遇到错误时，会直接把错误信息写到 `abstract` 列：

| 标注 | 含义 | 处理方式 |
|------|------|----------|
| （空） | 还没跑 enrichment | 跑 `enrich` |
| `[error: 429 rate-limited after 3 retries, please fetch manually]` | 429 重试 3 次后放弃 | 人工获取摘要，替换此字段 |
| `[error: HTTP 403, please fetch manually]` | HTTP 错误（无权限等） | 人工获取摘要 |
| `[error: Network error, please fetch manually]` | 网络问题 | 重新跑 `enrich` |
| `[abstract unavailable]` | 所有来源都没有摘要 | 人工获取摘要 |

在 spreadsheet 中搜索 `[error:` 可以快速定位所有错误项。

重新跑 `enrich` 时，带 `[error:]` 的论文会被自动识别为需要重试，无需手动清除。

---

## 各 Phase 完成状态（2026-04-08）

| Phase | 功能 | 状态 | 说明 |
|-------|------|------|------|
| A | DBLP HTML proceedings 解析 | ✅ 完成 | 429 重试 + 404 跳过 + 失败汇总 |
| B | S2 enrichment (via DOI) | ✅ 完成 | 429 指数退避重试 + 错误标注到 CSV |
| C | Abstract fallback (Crossref + arXiv) | ✅ 完成 | 429 指数退避重试 + 错误标注到 CSV |
| D | Score + merge-safe CSV + state | ✅ 完成 | merge-safe 写入 + 原子操作 |
| `enrich` | 独立 enrichment 命令 | ✅ 完成 | 默认只补缺失项，`--force` 全部重跑 |

### 已知问题

1. **作者列表不完整**：DBLP COinS 中 `rft.au` 只列出第一作者。需要从 HTML 的其他位置提取完整作者列表。
2. **DBLP 结构变更**：解析器依赖 DBLP HTML 的 CSS class 和 COinS 格式，如果 DBLP 改版需要适配。

### 待改进

- [ ] 完整作者列表提取（从 DBLP 详情页）
- [ ] 断点续爬（Phase B/C 中断后不重头开始）
- [ ] 日志文件输出（stderr 重定向到文件）
- [ ] 并发请求（async 或线程池）提高 enrichment 速度
