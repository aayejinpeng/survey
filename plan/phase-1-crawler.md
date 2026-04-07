# Phase 1: survey_crawler.py — DBLP + Enrichment（v2）

## 目标

从 DBLP proceedings 页面按 venue×year 获取论文，经 S2/Crossref/arXiv enrichment 后输出 CSV。

## 文件

- `workspace/survey/survey_crawler.py`

## CLI 接口

```bash
python3 survey_crawler.py crawl \
    --config .claude/survey-data/{topic}/config.yaml \
    --output .claude/survey-data/{topic}/abstracts.csv \
    --state  .claude/survey-data/{topic}/crawl-state.json \
    --mode   full|update
```

## 关键约定

1. `paper_id` 是 CSV 行主键：
   - 有 DOI → `doi:{doi}`
   - 无 DOI 有 arxiv_id → `arxiv:{arxiv_id}`
   - 都没有 → `s2:{s2_paper_id}`
2. `arxiv_id`、`s2_paper_id` 独立成列。
3. `keep` / `notes` 是人工列，任何写入策略只能保留或回填，不能置空覆盖。

## 实施步骤

### Step 1.1: 配置加载 + 状态管理

- `load_config(path)` → dict
- `load_state(path)` → dict（不存在则返回空）
- `save_state(path, state)` → 写 JSON

config.yaml 格式：
```yaml
topic: "CPU AI acceleration"
venues:
  - id: ISCA
    type: conference
    dblp_key: conf/isca
  - id: MICRO
    type: conference
    dblp_key: conf/micro
date_range:
  start: 2023
  end: 2026
enrichment:
  s2: { enabled: true }
  crossref: { enabled: true }
  arxiv: { enabled: true }
keywords: ["CPU", "tensor", "AMX", "SME", "RISC-V"]
update:
  overlap_years: 1
```

crawl-state.json 格式：
```json
{
  "topic_slug": "cpu-ai-acceleration",
  "last_full_crawl": "2026-04-07T14:30:00Z",
  "last_incremental_crawl": null,
  "seen_paper_ids": ["doi:10.1109/ISCA.2023.1234", "arxiv:2301.07041"],
  "crawled_venues": [
    {"venue": "ISCA", "year": 2024, "papers": 52, "crawled": "2026-04-07"}
  ],
  "crawl_history": []
}
```

### Step 1.2: DBLP Proceedings Fetch（HTML 解析）

**URL 格式**：`https://dblp.org/db/{dblp_key}/{abbr}{year}`

解析策略：
1. 用 `urllib.request` 获取 HTML
2. 解析 HTML 提取论文列表
3. 每篇论文提取：
   - `title`：`<span class="title">` 或 `<cite class="data">` 中的标题
   - `authors`：`<span itemprop="author">` 或 author links
   - `doi`：从电子版链接中提取 DOI
   - `url`：电子版链接
   - `venue`：config 中指定的 venue id
   - `year`：URL 中的年份
   - `type`：论文类型（只保留 "Conference and Workshop Papers"）
4. 过滤掉 editorial、preface、keynote 等非正式论文
5. 按 DOI 去重（同一论文可能出现在多个 venue proceedings 中）

```python
def fetch_venue_papers(venue_id: str, dblp_key: str, year: int) -> list[dict]:
    """Fetch all papers from a DBLP proceedings page."""
    abbr = dblp_key.split("/")[-1]  # e.g., "isca" from "conf/isca"
    url = f"https://dblp.org/db/{dblp_key}/{abbr}{year}"
    html = _fetch_html(url)
    papers = _parse_dblp_proceedings(html, venue_id, year)
    return papers
```

### Step 1.3: S2 Enrichment（via DOI）

对每篇有 DOI 的论文，调用 S2 `get_paper` API：
- 输入：`DOI:{doi}`
- 补充：`citation_count`, `abstract`, `s2_paper_id`, `venue`（如有更精确的）, `arxiv_id`（从 externalIds）
- rate limit：1.1s 间隔

```python
def enrich_from_s2(papers: list[dict], delay: float = 1.1) -> None:
    for paper in papers:
        if not paper.get("doi"):
            continue
        try:
            s2_data = s2_fetch.get_paper(f"DOI:{paper['doi']}", fields=...)
            paper["citation_count"] = s2_data.get("citationCount", 0) or 0
            paper["s2_paper_id"] = s2_data.get("paperId", "")
            if s2_data.get("abstract"):
                paper["abstract"] = s2_data["abstract"]
            ext = s2_data.get("externalIds") or {}
            if ext.get("ArXiv"):
                paper["arxiv_id"] = ext["ArXiv"]
        except Exception as exc:
            print(f"  [s2] {paper['doi']}: {exc}", file=sys.stderr)
        time.sleep(delay)
```

### Step 1.4: Abstract Fallback Chain

对 abstract 仍为空的论文，按优先级补全：

```python
def enrich_abstracts(papers: list[dict]) -> None:
    for paper in papers:
        if paper.get("abstract"):
            continue
        # Layer 1: Crossref (via DOI)
        if paper.get("doi") and _fill_from_crossref(paper):
            continue
        # Layer 2: arXiv (via arxiv_id)
        if paper.get("arxiv_id") and _fill_from_arxiv(paper):
            continue
        # Layer 3: Mark unavailable
        paper["abstract"] = "[abstract unavailable]"
```

Crossref API：
```python
def _fill_from_crossref(paper: dict) -> bool:
    url = f"https://api.crossref.org/works/{urllib.parse.quote(paper['doi'], safe='')}"
    data = _request_json(url)
    abstract = data.get("message", {}).get("abstract", "")
    if abstract:
        paper["abstract"] = _clean_crossref_abstract(abstract)
        return True
    return False
```

### Step 1.5: 关键词排序

- 用 `config.keywords` 对论文做简单关键词匹配打分
- 按得分降序排列（只影响默认顺序）

### Step 1.6: Merge-safe CSV 写入

- `full` 模式：刷新机器列，按 `paper_id` 回填已有 `keep`/`notes`
- `update` 模式：只追加 net-new `paper_id`，不覆盖已有行
- 原子写入（临时文件 + rename）

### Step 1.7: 状态更新

- 更新 `crawl-state.json`：
  - `seen_paper_ids`（追加新 paper_id）
  - `crawled_venues`（追加 venue×year 记录）
  - `crawl_history`（追加记录）

## 依赖

- Python 标准库（`csv`, `json`, `html.parser`, `urllib`）
- `PyYAML`
- `semantic_scholar_fetch.py`（import）
- `arxiv_fetch.py`（import，仅 abstract fallback）

## 验证

```bash
python3 survey_crawler.py crawl \
    --config test-config.yaml \
    --output /tmp/test-abstracts.csv \
    --state /tmp/test-state.json \
    --mode full
```

验收断言：
1. DBLP HTML 解析能正确提取 ISCA 2024 的论文列表
2. S2 enrichment 能补全 citation_count 和 abstract
3. Crossref fallback 能补全 S2 缺失的 abstract
4. full rerun 时旧 CSV 的 `keep`/`notes` 被保留
5. 同一 state 下连续 update 不重复追加
6. CSV 包含 `paper_id`, `arxiv_id`, `s2_paper_id` 三列

## 预估代码量

~400-500 行 Python
