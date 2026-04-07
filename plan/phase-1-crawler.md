# Phase 1: survey_crawler.py — 爬取编排器

## 目标

实现 `survey_crawler.py`，从 arXiv + Semantic Scholar 爬取论文元数据，输出 CSV。

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

## 实施步骤

### Step 1.1: 配置加载 + 状态管理

- `load_config(path)` → dict
- `load_state(path)` → dict（不存在则返回空）
- `save_state(path, state)` → 写 JSON

config.yaml 格式：
```yaml
topic: "CPU AI acceleration"
date_range:
  start: "2023-01-01"
  end: null
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

crawl-state.json 格式：
```json
{
  "topic_slug": "cpu-ai-acceleration",
  "last_full_crawl": "2026-04-07T14:30:00Z",
  "last_incremental_crawl": null,
  "seen_paper_ids": [],
  "crawl_history": []
}
```

### Step 1.2: arXiv 爬取

- 复用 `arxiv_fetch.py` 的 search 功能（import 为模块）
- 遍历 config 中的每个 query + category
- 提取：paper_id (arXiv ID), title, authors, year, abstract, categories, url, published_date
- source 标记为 `arxiv`
- citation_count 初始为 0（后续由 S2 补充）

关键：import 已有脚本
```python
TOOLS_DIR = os.path.join(os.path.dirname(__file__), '..',
    'sleep-work-agent/Auto-claude-code-research-in-sleep/tools')
sys.path.insert(0, TOOLS_DIR)
import arxiv_fetch
```

### Step 1.3: Semantic Scholar 爬取

- 复用 `semantic_scholar_fetch.py` 的 search 功能
- 遍历 config 中的每个 query
- 提取：paper_id (S2 paperId), title, authors, year, venue, abstract, citation_count, doi, url
- source 标记为 `semantic_scholar`
- 如果有 `externalIds.ArXiv`，也记录 arxiv_id 用于去重

### Step 1.4: S2 引用数补充

- 对 arXiv 论文，调用 S2 `paper` API (ARXIV:{id}) 补充 citation_count 和 venue
- rate limit: 1.1s 间隔，支持 SEMANTIC_SCHOLAR_API_KEY 环境变量

### Step 1.5: 去重 + 合并

- 主键：arXiv ID（arXiv 结果和 S2 结果中 externalIds.ArXiv 匹配的合并）
- S2-only 论文用 S2 paperId 作为 paper_id
- 合并时优先取更完整的记录

### Step 1.6: 关键词排序

- 用 config.keywords 对论文做简单关键词匹配打分
- 按得分降序排列（不影响 CSV 内容，只影响默认顺序）

### Step 1.7: CSV 写入

- 使用 Python csv 模块，quoting=QUOTE_ALL（处理摘要中的逗号/引号/换行）
- UTF-8 编码（BOM 头可选，方便 Excel 识别）
- full 模式：覆盖写入
- update 模式：读取已有 CSV，append 新行（保留已有 keep/notes）

### Step 1.8: 状态更新

- 更新 crawl-state.json：
  - last_full_crawl / last_incremental_crawl
  - seen_paper_ids（追加新 ID）
  - crawl_history（追加记录）

## 依赖

- Python 标准库（csv, json, yaml 需要 PyYAML 或手写简易 parser）
- arxiv_fetch.py（import）
- semantic_scholar_fetch.py（import）

## 验证

```bash
# 用窄查询测试
python3 survey_crawler.py crawl \
    --config test-config.yaml \
    --output /tmp/test-abstracts.csv \
    --state /tmp/test-state.json \
    --mode full
# 检查 CSV 列数、编码、去重是否正确
```

## 预估代码量

~300-400 行 Python
