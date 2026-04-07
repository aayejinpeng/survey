# Survey Pipeline — 总体方案

## Context

两套 pipeline：
1. **全量 Survey**：首次对某 topic 做系统文献扫描 → CSV → 人工筛选 → 引用图谱
2. **周更 Update**：增量爬取新论文，合并到已有 CSV，重新筛选+图谱

对比已有 `survey-all`（广度搜索+综述，markdown 输出），新 pipeline 是**结构化、可追踪、带引用图谱**的深度调研工具。

## 文件结构

```
workspace/survey/                          ← Python 工具
    survey_crawler.py                      ← 爬取编排器（arXiv + S2 → CSV）
    citation_graph.py                      ← 引用图谱构建+可视化
    plan/                                  ← 方案文档
        README.md                          ← 本文件
        phase-1-crawler.md                 ← Phase 1 实施细则
        phase-2-skills.md                  ← Phase 2 实施细则
        phase-3-graph.md                   ← Phase 3 实施细则
        phase-4-update.md                  ← Phase 4 实施细则

.claude/commands/survey/                   ← Claude Code Skills
    survey-crawl.md                        ← 步骤 1+2：爬取+CSV
    survey-filter.md                       ← 步骤 3：人工筛选
    survey-graph.md                        ← 步骤 4+5：引用图谱
    survey-update.md                       ← 步骤 6：周更增量

.claude/survey-data/{topic-slug}/          ← 运行时数据（gitignored）
    config.yaml
    crawl-state.json
    abstracts.csv
    abstracts-filtered.csv
    citation-cache.json
    citation-graph.dot / .png / -stats.md
```

## CSV Schema

| 列 | 类型 | 说明 |
|---|---|---|
| `paper_id` | string | arXiv ID 或 S2 paperId（去重主键）|
| `title` | string | 论文标题 |
| `authors` | string | 作者，分号分隔 |
| `year` | int | 发表年份 |
| `venue` | string | 会议/期刊/arXiv |
| `abstract` | string | 摘要全文 |
| `source` | string | `arxiv` / `semantic_scholar` |
| `categories` | string | arXiv 分类或 S2 fieldsOfStudy |
| `citation_count` | int | S2 引用数 |
| `url` | string | 论文链接 |
| `doi` | string | DOI（如有）|
| `published_date` | YYYY-MM-DD | 发表/提交日期 |
| `crawled_date` | YYYY-MM-DD | 爬取日期 |
| `keep` | string | **人工填写**：`yes`/`no`/`maybe`，默认空 |
| `notes` | string | **人工填写**：用户备注 |

## Pipeline 流程

```
/survey-crawl "topic"
    ↓ 生成 config.yaml + survey_crawler.py --mode full
    ↓ → abstracts.csv
    ↓ 提示用户去 spreadsheet 编辑 keep 列

/survey-filter "topic"
    ↓ 读取 abstracts.csv → 提取 keep=yes/maybe
    ↓ → abstracts-filtered.csv

/survey-graph "topic"
    ↓ citation_graph.py --input abstracts-filtered.csv
    ↓ S2 API 获取引用关系（filtered 集合内建边）
    ↓ → citation-graph.dot + .png + -stats.md

/survey-update "topic"
    ↓ 读取 crawl-state.json → last_crawl_date
    ↓ survey_crawler.py --mode update
    ↓ 合并到已有 abstracts.csv
    ↓ 提示用户筛选新行
```

## 关键设计决策

1. **survey_crawler.py**：复用已有 `arxiv_fetch.py` 和 `semantic_scholar_fetch.py`，import 为模块
2. **citation_graph.py**：第一阶段 matplotlib + networkx + DOT；后续升级 pyvis 交互式 HTML
3. **config.yaml**：用户手写，指定 venues/keywords/dates
4. **增量更新**：crawl-state.json 追踪时间戳 + seen_paper_ids，append 不覆盖

## 依赖

- 已安装：matplotlib, networkx
- 后续：pyvis（`pip install pyvis`）
- 已有工具：arxiv_fetch.py, semantic_scholar_fetch.py
