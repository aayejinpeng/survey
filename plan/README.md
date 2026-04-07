# Survey Pipeline — 总体方案（v2: Venue-Based）

## Context

两套 pipeline：
1. **全量 Survey**：按 venue+year 从 DBLP 精确获取论文 → CSV → 人工筛选 → 引用图谱
2. **周更 Update**：增量获取新年度论文，合并到已有 CSV，重新筛选+图谱

v1 按关键词搜 S2/arXiv → 噪音大、不可复现。
**v2 改为从 DBLP proceedings 页面按 venue+year 获取精确论文列表**，S2/Crossref/arXiv 仅做 enrichment。

## 文件结构

```
workspace/survey/                          ← Python 工具与方案文档
    survey_crawler.py                      ← 爬取编排器（DBLP + S2/Crossref/arXiv enrichment → CSV）
    citation_graph.py                      ← 引用图谱构建+可视化
    test_crawler.py                        ← 单元测试
    plan/                                  ← 方案文档
        README.md                          ← 本文件
        phase-1-crawler.md                 ← Phase 1 实施细则
        phase-2-skills.md                  ← Phase 2 实施细则
        phase-3-graph.md                   ← Phase 3 实施细则
        phase-4-update.md                  ← Phase 4 实施细则
    tests/fixtures/                        ← golden CSV / state fixtures

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

## 核心约定

1. `paper_id` 是 **CSV 行主键**，不是外部 API lookup key。
2. `paper_id` 采用带前缀的稳定格式：
   - 有 DOI 时：`doi:{doi}`（最稳定的跨系统对齐键）
   - 有 `arxiv_id` 无 DOI 时：`arxiv:{arxiv_id}`
   - 否则：`s2:{s2_paper_id}`
3. `s2_paper_id` 是 Phase 3 与 Semantic Scholar API 交互时的首选 ID。
4. `arxiv_id` 是 abstract fallback 时与 arXiv API 交互的 ID。
5. `keep` / `notes` 是人工资产。`full` 和 `update` 两种模式都必须保留，不能被脚本覆盖为空。

## Pipeline 流程

```
/survey-crawl "topic"
    ↓ 生成或复用 config.yaml（含 venue 列表 + 年份范围）
    ↓ Phase A: DBLP HTML proceedings → 每个 venue×year 的完整论文列表
    ↓ Phase B: S2 enrichment (via DOI) → citation_count, abstract, s2_paper_id
    ↓ Phase C: Abstract fallback → Crossref (DOI) → arXiv (arxiv_id) → 标记不可用
    ↓ Phase D: 关键词打分 + 排序 + merge-safe 写入 CSV
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
    ↓ survey_crawler.py --mode update（只爬新年度的 proceedings）
    ↓ append 到已有 abstracts.csv，保留人工列
    ↓ 提示用户筛选新行
```

## DBLP 获取策略：HTML Proceedings

URL 格式：`https://dblp.org/db/conf/{abbr}/{abbr}{year}`
- ISCA 2024: `https://dblp.org/db/conf/isca/isca2024`
- MICRO 2023: `https://dblp.org/db/conf/micro/micro2023`

优点：最完整、最精确、无噪音。

## CSV Schema

| 列 | 类型 | 说明 |
|---|---|---|
| `paper_id` | string | 稳定主键：`doi:{doi}` / `arxiv:{id}` / `s2:{id}` |
| `arxiv_id` | string | arXiv ID；没有则为空 |
| `s2_paper_id` | string | S2 paperId；enrichment 后填充 |
| `title` | string | 论文标题 |
| `authors` | string | 作者，分号分隔 |
| `year` | int | 发表年份 |
| `venue` | string | 会议/期刊（来自 DBLP）|
| `abstract` | string | 摘要（S2 → Crossref → arXiv 兜底）|
| `source` | string | `dblp` |
| `categories` | string | DBLP type 或 S2 fieldsOfStudy |
| `citation_count` | int | S2 引用数 |
| `url` | string | 论文链接 |
| `doi` | string | DOI（来自 DBLP）|
| `published_date` | YYYY-MM-DD | 发表/提交日期 |
| `crawled_date` | YYYY-MM-DD | 爬取日期 |
| `keep` | string | **人工填写**：`yes` / `no` / `maybe`，默认空 |
| `notes` | string | **人工填写**：用户备注 |

## config.yaml 格式

```yaml
topic: "CPU AI acceleration"

venues:
  - id: ISCA
    type: conference
    dblp_key: conf/isca
  - id: MICRO
    type: conference
    dblp_key: conf/micro
  - id: HPCA
    type: conference
    dblp_key: conf/hpca

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

keywords: ["CPU", "tensor", "AMX", "SME", "RISC-V"]
update:
  overlap_years: 1
```

## 阶段 Gate

| Gate | 通过条件 |
|------|----------|
| Gate 0 | config venue 列表 + DBLP HTML 解析连通 |
| Gate 1 | venue×year 获取 + S2 enrichment + abstract fallback + CSV 输出 |
| Gate 2 | `/survey-crawl` 与 `/survey-filter` 端到端跑通 |
| Gate 3 | mixed-ID filtered CSV 可正常出图 |
| Gate 4 | 增量 update 不重复追加 |

## 依赖

- DBLP proceedings HTML（免费，无需 key）
- Semantic Scholar API（可选 key）
- Crossref API（免费，polite pool with mailto）
- arXiv API（免费）
- Python: PyYAML, networkx, matplotlib
