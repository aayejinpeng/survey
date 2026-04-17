# Survey Pipeline v3 — 模块化架构

## 核心思路

每个脚本独立运行，输入输出明确，数据按目录分层。一个 enriched 数据可服务多个 topic。

## 架构总览

```
configs/venues.yaml                      # 全局会议/期刊配置
configs/topic-*.yaml                     # 各主题关键词配置

fetch_dblp.py → data/db/                 # Step 1: DBLP 抓取
enrich_papers.py → data/enriched/        # Step 2: S2/Crossref/arXiv 富化
score_papers.py → data/topics/{topic}/   # Step 3: 加权打分
slice_csv.py                             # Step 3.5: 按阈值截取
review_server.py + review.html           # Step 4: Web 审阅 + 标记
sync_zotero.py → pdfs/                   # Step 5: Zotero PDF 同步
build_graph.py                           # Step 6: 引用图（待做）

skill/claude/analyze-paper-claude.md     # Claude Code skill: 论文分析
```

## 目录结构

```
workspace/survey/
  fetch_dblp.py          ← Step 1
  enrich_papers.py       ← Step 2
  score_papers.py        ← Step 3
  slice_csv.py           ← Step 3.5
  review_server.py       ← Step 4 服务端
  review.html            ← Step 4 前端
  sync_zotero.py         ← Step 5
  requirements.txt       ← pip 依赖

  configs/
    venues.yaml          ← 会议/期刊 + DBLP key
    topic-cpu-ai.yaml    ← topic 关键词 + 权重

  tools/
    s2_fetch.py          ← S2 batch API 客户端
    arxiv_fetch.py       ← arXiv API 客户端

  data/
    db/                  ← 103 CSV，原始 DBLP 数据
    enriched/            ← 103 CSV，富化后数据
    topics/
      cpu-ai/            ← 打分结果
        scored.csv       # 全量 + top10/50/100
        scored-score-gte11.csv
        doi-list.txt     # keep 论文 DOI

  pdfs/                  ← PDF 下载目录
  skill/
    claude/
      analyze-paper-claude.md  ← Claude Code 论文分析 skill
  plan/                  ← 设计文档
  doc/                   ← 用户手册
```

## 数据流

```
configs/venues.yaml
       ↓
  fetch_dblp.py
       ↓
  data/db/{venue}-{year}.csv
       ↓
  enrich_papers.py (S2 batch → Crossref → arXiv)
       ↓
  data/enriched/{venue}-{year}.csv
       ↓
  score_papers.py + configs/topic-*.yaml
       ↓
  data/topics/{topic}/scored.csv + top{10,50,100}.csv
       ↓
  slice_csv.py → scored-score-gte{N}.csv
       ↓
  review_server.py → Web 审阅标记 (keep/core/related/skip)
       ↓
  sync_zotero.py → pdfs/
       ↓
  build_graph.py → citation-graph.* (待做)
```

## CSV Schema

### DBLP 阶段 (data/db/)

| 列 | 说明 |
|----|------|
| paper_id | `doi:{doi}` 或 `dblp:{dblp_id}` |
| title | 论文标题 |
| authors | 分号分隔 |
| year | 发表年份 |
| venue | 会议/期刊 ID |
| doi | DOI |
| url | DOI 或 DBLP 链接 |
| dblp_id | DBLP record ID |

### Enriched 阶段 (data/enriched/)

在 DBLP 基础上增加：

| 列 | 说明 |
|----|------|
| arxiv_id | arXiv ID（从 S2 获取） |
| s2_paper_id | Semantic Scholar ID |
| abstract | 摘要（S2/Crossref/arXiv 三层 fallback） |
| source | `dblp` |
| categories | fieldsOfStudy |
| citation_count | S2 引用数 |
| published_date | 发表日期 |
| crawled_date | 抓取日期 |
| keep | 用户标记 |
| notes | 用户备注 |

### Scored 阶段 (data/topics/)

在 Enriched 基础上增加：

| 列 | 说明 |
|----|------|
| relevance_score | 加权得分 |
| matched_keywords | 匹配到的关键词列表 |
| relevance | High/Medium/Low/None 标签 |

## Skill: 论文分析

`skill/claude/analyze-paper-claude.md` 是 Claude Code 的 skill 文件，用于：

- 读取 corpus 中的论文 JSON（`abstract` + `body_text`）
- 输出结构化 JSON dossier，包含：
  - 研究目的、意义、贡献点
  - 主题簇分类（9 类）
  - 工作映射（3 条工作线）
  - 关键技术、实验结果
  - Gap 识别和 proposal 论据

该 skill 用于辅助 proposal writing，提供从论文到论证素材的半自动转化。

## 详细设计

- [Step 1: fetch_dblp](step1-fetch-dblp.md) — DBLP 抓取
- [Step 2: enrich_papers](step2-enrich-papers.md) — S2/Crossref/arXiv 富化
- [Step 3: score_papers](step3-score-papers.md) — 关键词打分
- [Step 4: review_server](step4-review.md) — Web 审阅
- [Step 5: sync_zotero](step5-sync-zotero.md) — Zotero PDF 同步
- [Step 6: build_graph](step6-build-graph.md) — 引用图
