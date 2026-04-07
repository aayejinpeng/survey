# Survey Pipeline — 总体方案

## Context

两套 pipeline：
1. **全量 Survey**：首次对某 topic 做系统文献扫描 → CSV → 人工筛选 → 引用图谱
2. **周更 Update**：增量爬取新论文，合并到已有 CSV，重新筛选+图谱

对比已有 `survey-all`（广度搜索+综述，markdown 输出），新 pipeline 是**结构化、可追踪、带引用图谱**的深度调研工具。

## 文件结构

```
workspace/survey/                          ← Python 工具与方案文档
    survey_crawler.py                      ← 爬取编排器（arXiv + S2 → CSV）
    citation_graph.py                      ← 引用图谱构建+可视化
    plan/                                  ← 方案文档
        README.md                          ← 本文件
        phase-1-crawler.md                 ← Phase 1 实施细则
        phase-2-skills.md                  ← Phase 2 实施细则
        phase-3-graph.md                   ← Phase 3 实施细则
        phase-4-update.md                  ← Phase 4 实施细则
    tests/fixtures/                        ← 建议新增：golden CSV / state fixtures

.claude/commands/survey/                   ← Claude Code Skills
    survey-crawl.md                        ← 步骤 1+2：爬取+CSV
    survey-filter.md                       ← 步骤 3：人工筛选
    survey-graph.md                        ← 步骤 4+5：引用图谱
    survey-update.md                       ← 步骤 6：周更增量

.claude/survey-data/{topic-slug}/          ← 运行时数据（建议保持 gitignored）
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
   - 有 `arxiv_id` 时：`arxiv:{arxiv_id}`
   - 否则：`s2:{s2_paper_id}`
3. `s2_paper_id` 是 Phase 3 / Phase 4 与 Semantic Scholar API 交互时的首选 ID。
4. 如果某行只有 `arxiv_id` 没有 `s2_paper_id`，图谱阶段先用 `ARXIV:{arxiv_id}` resolve 一次，并把结果缓存回 `citation-cache.json`。
5. `keep` / `notes` 是人工资产。`full` 和 `update` 两种模式都必须保留，不能被脚本覆盖为空。

## CSV Schema

| 列 | 类型 | 说明 |
|---|---|---|
| `paper_id` | string | 稳定主键：`arxiv:{id}` 或 `s2:{paperId}` |
| `arxiv_id` | string | arXiv ID；没有则为空 |
| `s2_paper_id` | string | Semantic Scholar paperId；没有则为空 |
| `title` | string | 论文标题 |
| `authors` | string | 作者，分号分隔 |
| `year` | int | 发表年份 |
| `venue` | string | 会议/期刊/arXiv |
| `abstract` | string | 摘要全文 |
| `source` | string | `arxiv` / `semantic_scholar` |
| `categories` | string | arXiv 分类或 S2 fieldsOfStudy |
| `citation_count` | int | S2 引用数 |
| `url` | string | 论文链接 |
| `doi` | string | DOI（如有） |
| `published_date` | YYYY-MM-DD | 发表/提交日期 |
| `crawled_date` | YYYY-MM-DD | 爬取日期 |
| `keep` | string | **人工填写**：`yes` / `no` / `maybe`，默认空 |
| `notes` | string | **人工填写**：用户备注 |

## Pipeline 流程

```
/survey-crawl "topic"
    ↓ 生成或复用 config.yaml（默认生成初稿，用户可按需手改）
    ↓ survey_crawler.py --mode full
    ↓ 刷新机器列，并按 paper_id 回填已有 keep/notes
    ↓ → abstracts.csv
    ↓ 提示用户去 spreadsheet 编辑 keep 列

/survey-filter "topic"
    ↓ 读取 abstracts.csv → 提取 keep=yes/maybe
    ↓ → abstracts-filtered.csv

/survey-graph "topic"
    ↓ citation_graph.py --input abstracts-filtered.csv
    ↓ 优先使用 s2_paper_id；缺失时用 ARXIV:{arxiv_id} resolve
    ↓ S2 API 获取引用关系（filtered 集合内建边）
    ↓ → citation-graph.dot + .png + -stats.md

/survey-update "topic"
    ↓ 读取 crawl-state.json → last_crawl_date
    ↓ 计算 effective_start = last_crawl_date - overlap_days
    ↓ survey_crawler.py --mode update
    ↓ client-side 过滤日期窗口 + seen_paper_ids 去重
    ↓ append 到已有 abstracts.csv，并保留人工列
    ↓ 提示用户筛选新行
```

## 关键设计决策

1. **survey_crawler.py**：复用已有 `arxiv_fetch.py` 和 `semantic_scholar_fetch.py`，import 为模块。
2. **config.yaml**：由 `/survey-crawl` 先生成默认配置，后续允许用户手动编辑复用。
3. **full / update 写入策略**：统一采用 merge-safe 写法，机器列可刷新，人工列只回填不清空。
4. **增量更新策略**：`crawl-state.json` 追踪时间戳 + `seen_paper_ids`；S2 采用 overlap window + client-side 过滤，不只依赖 `year`。
5. **citation_graph.py**：第一阶段 matplotlib + networkx + DOT；后续再升级 pyvis 交互式 HTML。

## 阶段 Gate

| Gate | 通过条件 |
|------|----------|
| Gate 0 | `paper_id / arxiv_id / s2_paper_id` contract 定稿，fixture 样例齐全 |
| Gate 1 | full crawl 在混合 arXiv/S2 样本上能正确 dedupe，并保留已有 `keep/notes` |
| Gate 2 | `/survey-crawl` 与 `/survey-filter` 端到端跑通；重复运行同 topic 不丢人工列 |
| Gate 3 | mixed-ID `abstracts-filtered.csv` 能正常出图、出 DOT、出 stats |
| Gate 4 | 同一时间窗口连续执行两次 update，第二次应为 0 new papers 或仅刷新状态，不重复追加 |

## 依赖

- 已安装：`PyYAML`、`matplotlib`、`networkx`
- 后续可选：`pyvis`
- 已有工具：`arxiv_fetch.py`、`semantic_scholar_fetch.py`
