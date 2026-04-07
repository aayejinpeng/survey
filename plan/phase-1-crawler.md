# Phase 1: survey_crawler.py — 爬取编排器

## 目标

实现 `survey_crawler.py`，从 arXiv + Semantic Scholar 爬取论文元数据，输出可复用、可增量更新的 CSV。

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

1. `paper_id` 是 CSV 行主键，格式固定为：
   - `arxiv:{arxiv_id}`
   - `s2:{s2_paper_id}`
2. `paper_id` 不直接用于 Semantic Scholar API。
3. `arxiv_id`、`s2_paper_id` 必须单独落列，供去重、补全和图谱阶段复用。
4. `keep` / `notes` 是人工列，任何写入策略都只能保留或回填，不能置空覆盖。

## 实施步骤

### Step 1.1: 配置加载 + 状态管理

- `load_config(path)` → dict
- `load_state(path)` → dict（不存在则返回空）
- `save_state(path, state)` → 写 JSON

`config.yaml` 格式：
```yaml
topic: "CPU AI acceleration"
date_range:
  start: "2023-01-01"
  end: null
update:
  overlap_days: 7
arxiv:
  categories: ["cs.AR", "cs.PF"]
  queries: ["CPU matrix extension AI", "tensor unit RISC-V"]
  max_per_query: 50
semantic_scholar:
  queries: ["CPU AI acceleration tensor unit"]
  fields_of_study: "Computer Science,Engineering"
  publication_types: "JournalArticle,Conference"
  min_citations: 5
  max_per_query: 50
keywords: ["CPU", "tensor", "AMX", "SME", "RISC-V"]
```

`crawl-state.json` 格式：
```json
{
  "topic_slug": "cpu-ai-acceleration",
  "last_full_crawl": "2026-04-07T14:30:00Z",
  "last_incremental_crawl": null,
  "seen_paper_ids": ["arxiv:2301.07041", "s2:abc123def456"],
  "crawl_history": []
}
```

### Step 1.2: arXiv 爬取

- 复用 `arxiv_fetch.py` 的 `search()` 功能
- 遍历 config 中的每个 query + category
- 提取：
  - `paper_id = arxiv:{arxiv_id}`
  - `arxiv_id`
  - `s2_paper_id = ""`
  - `title`, `authors`, `year`, `abstract`, `categories`, `url`, `published_date`
- `source` 标记为 `arxiv`
- `citation_count` 初始为 `0`，后续由 Step 1.4 补充

关键：import 已有脚本
```python
TOOLS_DIR = os.path.join(
    os.path.dirname(__file__),
    "..",
    "sleep-work-agent/Auto-claude-code-research-in-sleep/tools",
)
sys.path.insert(0, TOOLS_DIR)
import arxiv_fetch
import semantic_scholar_fetch
```

### Step 1.3: Semantic Scholar 爬取

- 复用 `semantic_scholar_fetch.py` 的 `search()` 功能
- 遍历 config 中的每个 query
- 提取：
  - `s2_paper_id = paperId`
  - `arxiv_id = externalIds.ArXiv`（如有）
  - 有 `arxiv_id` 时，`paper_id = arxiv:{arxiv_id}`
  - 否则，`paper_id = s2:{s2_paper_id}`
  - `title`, `authors`, `year`, `venue`, `abstract`, `citation_count`, `doi`, `url`
- `source` 标记为 `semantic_scholar`

### Step 1.4: S2 补充字段

- 对 arXiv 论文调用 S2 `paper` API：`ARXIV:{arxiv_id}`
- 补充：
  - `citation_count`
  - `venue`
  - `doi`
  - `s2_paper_id`（如果 resolve 成功）
- rate limit：1.1s 间隔
- 支持 `SEMANTIC_SCHOLAR_API_KEY` 环境变量

### Step 1.5: 去重 + 记录合并

- 匹配顺序：
  1. `arxiv_id`
  2. 规范化后的 `doi`
  3. `s2_paper_id`
- 合并策略：
  - 机器列优先保留更完整、非空、更新的值
  - `paper_id` 优先采用 `arxiv:{id}`，否则 `s2:{id}`
  - `keep` / `notes` 不参与 crawler 内部合并，统一在写 CSV 时从旧文件回填

### Step 1.6: 关键词排序

- 用 `config.keywords` 对论文做简单关键词匹配打分
- 按得分降序排列
- 排序只影响 CSV 的默认顺序，不改变主键与去重结果

### Step 1.7: CSV 写入

- 使用 Python `csv` 模块，`quoting=QUOTE_ALL`
- UTF-8 编码
- 统一采用“先生成完整新内容，再 merge 旧人工列，最后原子写入”的策略
- `full` 模式：
  - 刷新整份机器数据
  - 如果输出 CSV 已存在，按 `paper_id` 回填旧的 `keep` / `notes`
  - 不能因为 full rerun 丢失人工筛选结果
- `update` 模式：
  - 读取已有 CSV
  - 只追加 net-new `paper_id`
  - 已有行不重写人工列
  - 建议使用临时文件 + rename 保证写入原子性

### Step 1.8: 状态更新

- 更新 `crawl-state.json`：
  - `last_full_crawl` / `last_incremental_crawl`
  - `seen_paper_ids`（写入 canonical `paper_id`）
  - `crawl_history`（追加记录）
- `crawl_history` 记录建议包含：
  - `date`
  - `mode`
  - `effective_start`
  - `effective_end`
  - `new_papers`
  - `total_unique`

## 依赖

- Python 标准库（`csv`、`json`、`datetime`）
- `PyYAML`
- `arxiv_fetch.py`
- `semantic_scholar_fetch.py`

## 验证

```bash
# 用窄查询测试
python3 survey_crawler.py crawl \
    --config test-config.yaml \
    --output /tmp/test-abstracts.csv \
    --state /tmp/test-state.json \
    --mode full
```

验收至少覆盖以下断言：

1. mixed-source fixture 能正确合并 arXiv / S2 重复项。
2. rerun full crawl 时，旧 CSV 里的 `keep` / `notes` 会被完整保留。
3. 同一 `crawl-state.json` 下连续执行两次 update，第二次不会重复追加同一 `paper_id`。
4. 输出 CSV 包含 `paper_id`、`arxiv_id`、`s2_paper_id` 三列，供后续 graph/update 复用。

## 预估代码量

~350-450 行 Python
