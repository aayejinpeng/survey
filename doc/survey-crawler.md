# Survey Crawler — 用户手册

## 概览

`survey_crawler.py` 是一个 venue-based 文献调研工具，按用户指定的会议/期刊 + 年份范围从 DBLP 获取论文，再通过多个 API 补充元数据，最终输出结构化 CSV 供人工筛选。

## Pipeline 四个阶段

```
config.yaml
    ↓
┌─────────────────────────────────────────────────────┐
│ Phase A: DBLP Fetch                                 │
│   指定 venue × year → 抓取 DBLP proceedings 页面    │
│   提取: title, authors, DOI, venue, year             │
│   输出: 论文列表 (无 abstract, 无 citation_count)    │
├─────────────────────────────────────────────────────┤
│ Phase B: S2 Enrichment                              │
│   用 DOI 查 Semantic Scholar                        │
│   补充: citation_count, abstract, s2_paper_id,      │
│         arxiv_id, fieldsOfStudy                     │
├─────────────────────────────────────────────────────┤
│ Phase C: Abstract Fallback                          │
│   对仍缺失 abstract 的论文，按优先级补全:           │
│   1. Crossref API (via DOI)                         │
│   2. arXiv API (via arxiv_id)                       │
│   3. 标记 [abstract unavailable]                    │
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

**限制**：
- 依赖 DBLP HTML 结构（如果 DBLP 改版需要调整解析器）
- 每个 proceedings 页面一次 HTTP 请求
- 无 rate limit 问题

---

## Phase B: S2 Enrichment

**功能**：用 DOI 逐篇查 Semantic Scholar，补充引用数和摘要。

**数据源**：Semantic Scholar `get_paper` API
- 输入：`DOI:{doi}`
- 补充字段：`citation_count`, `abstract`, `s2_paper_id`, `arxiv_id`（从 externalIds）, `fieldsOfStudy`

**rate limit**：
- 无 API key：~1 req/s
- 有 API key（环境变量 `SEMANTIC_SCHOLAR_API_KEY`）：更高限额
- 脚本默认 1.1s 间隔

**跳过方式**：`--no-s2` 或 `--no-enrich`

**限制**：
- S2 可能未收录某些 DOI（特别是非常新的论文）
- 在无 API key 情况下容易触发 429 rate limit
- 每篇论文一次 API 调用，数百篇论文需要数分钟

---

## Phase C: Abstract Fallback

**功能**：对 Phase B 后仍缺失 abstract 的论文，尝试其他来源补全。

**Fallback 链**：
1. **Crossref API**（via DOI）：大多数 IEEE/ACM/Springer 论文可获取
   - 免费无需 key
   - 支持 polite pool（设置 mailto 可提高速率）
2. **arXiv API**（via arxiv_id）：有预印本的论文
   - 需要 Phase B 先从 S2 获取到 arxiv_id
3. **标记 `[abstract unavailable]`**：以上均无法获取时

**跳过方式**：`--no-enrich` 跳过整个 Phase C

**限制**：
- Crossref 不是所有 DOI 都有 abstract
- arXiv 需要先有 arxiv_id（来自 S2 enrichment）
- 如果 Phase B 被跳过，Phase C 的 arXiv 层也基本无效（没有 arxiv_id）

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

## 使用方法

### 基本命令

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

# 增量更新
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

### config.yaml 格式

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

## 各 Phase 完成状态（2026-04-08）

| Phase | 功能 | 状态 | 说明 |
|-------|------|------|------|
| A | DBLP HTML proceedings 解析 | ✅ 完成 | ISCA 2024: 87篇, MICRO 2024: 115篇 验证通过 |
| B | S2 enrichment (via DOI) | ✅ 代码完成 | 需 API key 或等待 rate limit 过后测试 |
| C | Abstract fallback (Crossref + arXiv) | ✅ 代码完成 | 需联网测试 |
| D | Score + merge-safe CSV + state | ✅ 完成 | 10 个单元测试全通过 |
| — | 命令行进度输出 | ⬜ 需改进 | 当前输出信息不够清晰 |
| — | 错误恢复/断点续爬 | ⬜ 待做 | 当前中断后需重跑 |

### 已知问题

1. **S2 rate limit**：无 API key 时，连续调用几百次会触发 429。建议设置 `SEMANTIC_SCHOLAR_API_KEY` 环境变量。
2. **arXiv rate limit**：类似问题，间隔 1s 通常够用但大批量可能触发。
3. **DBLP 结构变更**：解析器依赖 DBLP HTML 的 CSS class 和 COinS 格式，如果 DBLP 改版需要适配。
4. **作者列表不完整**：DBLP COinS 中 `rft.au` 只列出第一作者。需要从 HTML 的其他位置提取完整作者列表。

### 待改进

- [ ] 进度条/百分比输出（Phase B/C 的逐篇处理）
- [ ] 断点续爬（Phase B/C 中断后不重头开始）
- [ ] 完整作者列表提取
- [ ] 日志文件输出（stderr 重定向到文件）
- [ ] 并发请求（async 或线程池）提高 enrichment 速度
