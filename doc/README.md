# Survey Docs

`workspace/survey/doc/` 保存面向使用者的文档入口。

当前 pipeline 已经从早期一体化 `survey_crawler.py`，切换为按步骤拆分的模块化流程：

1. `fetch_dblp.py`
2. `enrich_papers.py`
3. `score_papers.py`
4. `review_server.py` + `review.html`（Web 审阅）
5. `sync_zotero.py`（PDF 同步）
6. `build_graph.py`（计划中）

## 当前状态

| Step | 文档 | 脚本状态 | 说明 |
|------|------|----------|------|
| 1 | [step1-fetch-dblp.md](step1-fetch-dblp.md) | ✅ 已实现 | 抓 DBLP venue/year 论文列表 |
| 2 | [step2-enrich-papers.md](step2-enrich-papers.md) | ✅ 已实现 | 补摘要、引用数、S2/arXiv 标识 |
| 3 | [step3-score-papers.md](step3-score-papers.md) | ✅ 已实现 | 按 topic 配置关键词打分 |
| 3.5 | — | ✅ 已实现 | `slice_csv.py` 按 score 阈值截取 |
| 4 | [step4-review.md](step4-review.md) | ✅ 已实现 | Web 审阅界面，标记 keep/skip 并写回 CSV |
| 5 | [step5-sync-zotero.md](step5-sync-zotero.md) | ✅ 已实现 | 从 Zotero 本地 API 同步 PDF |
| 6 | [step6-build-graph.md](step6-build-graph.md) | ⬜ 计划中 | 引用图谱可视化 |

## 推荐阅读顺序

1. 先看 [survey-crawler.md](survey-crawler.md) 了解整体工作流
2. 再看 Step 1-3 文档，按顺序执行主链路
3. Step 4 使用 Web 审阅工具筛选论文
4. Step 5 同步 PDF 到本地
5. 如需引用图谱，见 Step 6 文档

## 当前推荐工作流

```text
configs/venues.yaml
      ↓
fetch_dblp.py
      ↓
data/db/{venue}-{year}.csv
      ↓
enrich_papers.py
      ↓
data/enriched/{venue}-{year}.csv
      ↓
score_papers.py + configs/topic-*.yaml
      ↓
data/topics/{topic}/scored.csv
      ↓
slice_csv.py → scored-score-gte{N}.csv
      ↓
review_server.py → Web 审阅标记 (keep/core/related/skip)
      ↓
sync_zotero.py → pdfs/
      ↓
build_graph.py (计划中)
```

## 关键目录

| 路径 | 用途 |
|------|------|
| `configs/venues.yaml` | Step 1 的全局 venue 配置 |
| `configs/topic-*.yaml` | Step 3 的 topic 配置 |
| `data/db/` | Step 1 输出 |
| `data/enriched/` | Step 2 输出 |
| `data/topics/{topic}/` | Step 3 及后续 topic 结果 |
| `pdfs/` | Step 5 PDF 下载目录 |
| `skill/` | Claude Code skills（论文分析等） |
| `plan/` | 方案与时间线 |

## Skill 目录

`skill/` 目录存放 Claude Code 专用的 skill 文件，用于辅助论文分析：

| Skill | 说明 |
|-------|------|
| `skill/claude/analyze-paper-claude.md` | 分析 corpus 中的论文 JSON，生成结构化 dossier |

使用方式：通过 Claude Code CLI 的 skill 功能调用，自动分析论文内容并生成用于 proposal writing 的结构化 JSON 输出。

## 说明

- 当前文档会优先反映"脚本实际可运行的行为"。
- `survey_crawler.py` 仍保留在仓库中，但不是当前推荐入口。
- Step 4 原计划为 `filter_papers.py`，实际改为 Web 审阅方案（`review_server.py`），体验更好。
