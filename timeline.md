# Survey Pipeline — Timeline（v3 模块化架构）

## 基线

- v1: 按 keyword 搜 S2/arXiv（已废弃）
- v2: 单文件 survey_crawler.py（已删除）
- **v3: 模块化，每个 step 独立脚本，数据按目录分层**

## 架构

```
venues.yaml                          # 会议/期刊配置
configs/topic-*.yaml                 # 主题关键词配置

fetch_dblp.py → data/db/             # Step 1: DBLP 抓取
enrich_papers.py → data/enriched/    # Step 2: S2/Crossref/arXiv 富化
score_papers.py → data/topics/{topic}/  # Step 3: 关键词打分
slice_csv.py                         # Step 3.5: 按 score 截取子集
review_server.py + review.html       # Step 4: Web 审阅
sync_zotero.py → pdfs/               # Step 5: Zotero PDF 同步
```

## Pipeline 状态

| Step | 脚本 | 状态 | 说明 |
|------|------|------|------|
| 1 | `fetch_dblp.py` | ✅ 完成 | DBLP 会议+期刊抓取，支持多页、自定义缩写 |
| 2 | `enrich_papers.py` | ✅ 完成 | S2 batch + Crossref + arXiv 三层富化 |
| 3 | `score_papers.py` | ✅ 完成 | 按 topic config 加权打分，输出 top-N |
| 3.5 | `slice_csv.py` | ✅ 完成 | 按 score 阈值截取 CSV |
| 4 | `review_server.py` | ✅ 完成 | 本地 Web 审阅，2x2 网格，关键词金色高亮 |
| 5 | `sync_zotero.py` | ✅ 完成 | 从 Zotero 本地 API 同步 PDF |
| 6 | `build_graph.py` | ⬜ 待做 | 引用图可视化 |

## 数据概览（2026-04-08）

- **103 个 venue×year CSV**，共 ~14,600 篇论文
- **会议 27 个**：ISCA, MICRO, HPCA, ASPLOS, OSDI, SOSP, EuroSys, USENIX-ATC, DAC, DATE, ICCAD, ICCD, SC, PACT, IPDPS, ICS, PLDI, CGO 等
- **期刊 7 个**：IEEE TC, CAL, TCAD, TPDS, TVLSI, IEEE Micro, ACM TACO
- **年份范围**：2022-2026
- **摘要覆盖率**：~92%（S2 batch + Crossref + arXiv）
- **CPU AI 主题**：score >= 11 共 196 篇，其中 12 篇标记 keep

## 变更记录

| 日期 | 变更 |
|------|------|
| 2026-04-07 | v1 启动 |
| 2026-04-07 | v2 改为 DBLP venue-based |
| 2026-04-08 | v3 模块化拆分，6 个独立脚本 |
| 2026-04-08 | 完成 Step 1-3 全量跑通（14,600 篇） |
| 2026-04-08 | 新增期刊支持（index → volume 解析） |
| 2026-04-08 | 新增 ASPLOS 多页探测、IPDPS dblp_abbr |
| 2026-04-08 | 完成 review_server.py Web 审阅工具 |
| 2026-04-08 | 完成 sync_zotero.py PDF 同步 |
