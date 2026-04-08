# Survey Pipeline

面向体系结构 / 计算机系统论文调研的模块化流水线。从 DBLP 按会议/期刊抓取论文，经 S2/Crossref/arXiv 富化摘要，按主题关键词打分，通过 Web 工具审阅标记，最终从 Zotero 同步 PDF。

## Pipeline 状态

| Step | 脚本 | 状态 | 输出 |
|------|------|------|------|
| 1 | `fetch_dblp.py` | ✅ | `data/db/*.csv` |
| 2 | `enrich_papers.py` | ✅ | `data/enriched/*.csv` |
| 3 | `score_papers.py` | ✅ | `data/topics/{topic}/scored.csv + top{10,50,100}.csv` |
| 3.5 | `slice_csv.py` | ✅ | 按 score 阈值截取 |
| 4 | `review_server.py` + `review.html` | ✅ | Web 审阅，标记写回 CSV |
| 5 | `sync_zotero.py` | ✅ | `pdfs/` |
| 6 | `build_graph.py` | ⬜ | 引用图可视化 |

## 当前数据（2026-04-08）

- **14,600 篇论文**，103 个 venue×year CSV
- **27 个会议** + **7 个期刊**，覆盖 2022-2026
- **摘要覆盖率 92%**
- CPU AI 主题：score >= 11 共 196 篇，12 篇已标记 keep

## 目录结构

```
survey/
├── configs/
│   ├── venues.yaml              # 会议/期刊 DBLP 配置
│   └── topic-cpu-ai.yaml        # 主题关键词（term + weight）
├── data/
│   ├── db/                      # 103 CSV，原始 DBLP 数据
│   ├── enriched/                # 103 CSV，富化后数据
│   └── topics/cpu-ai/           # 打分 + 截取结果
│       ├── scored.csv           # 全量 14,600 篇
│       ├── scored-score-gte11.csv  # 196 篇
│       ├── top10/50/100.csv
│       └── doi-list.txt         # keep 论文的 DOI 列表
├── pdfs/                        # PDF 下载目录
├── tools/
│   └── s2_fetch.py              # S2 batch API 客户端
├── fetch_dblp.py                # Step 1: DBLP 抓取
├── enrich_papers.py             # Step 2: S2/Crossref/arXiv 富化
├── score_papers.py              # Step 3: 关键词打分
├── slice_csv.py                 # Step 3.5: CSV 截取
├── review_server.py             # Step 4: Web 审阅服务端
├── review.html                  # Step 4: Web 审阅前端
├── sync_zotero.py               # Step 5: Zotero PDF 同步
├── survey_crawler.py            # (旧版，保留)
├── timeline.md                  # 时间线
├── doc/                         # 详细文档
└── plan/                        # 各 step 设计文档
```

## 快速开始

```bash
# Step 1: 从 DBLP 抓取论文列表
python3 fetch_dblp.py --config configs/venues.yaml --output-dir data/db/

# Step 2: 富化摘要和引用数（S2 batch → Crossref → arXiv）
python3 enrich_papers.py --input-dir data/db/ --output-dir data/enriched/

# Step 3: 按主题关键词打分
python3 score_papers.py --input-dir data/enriched/ \
    --topic-config configs/topic-cpu-ai.yaml \
    --output-dir data/topics/cpu-ai/

# Step 3.5: 截取高分子集
python3 slice_csv.py --input data/topics/cpu-ai/scored.csv --min-score 11

# Step 4: 启动 Web 审阅（浏览器打开 http://localhost:8088）
python3 review_server.py \
    --csv data/topics/cpu-ai/scored-score-gte11.csv \
    --topic configs/topic-cpu-ai.yaml

# Step 5: 从 Zotero 同步 PDF
python3 sync_zotero.py \
    --input data/topics/cpu-ai/scored-score-gte11.csv \
    --output-dir pdfs/cpu-ai/
```

## 数据流

```
configs/venues.yaml
      ↓
fetch_dblp.py → data/db/{venue}-{year}.csv
      ↓
enrich_papers.py → data/enriched/{venue}-{year}.csv
      ↓                          (S2 batch + Crossref + arXiv)
score_papers.py + configs/topic-*.yaml
      ↓
data/topics/{topic}/scored.csv
      ↓
slice_csv.py → scored-score-gte{N}.csv
      ↓
review_server.py → Web 审阅标记 (keep/core/skip)
      ↓
sync_zotero.py → pdfs/  (从 Zotero 本地 API 拉 PDF)
```

## 配置说明

### venues.yaml

```yaml
venues:
  - id: ISCA
    dblp_key: conf/isca          # 会议
  - id: IPDPS
    dblp_key: conf/ipps          # key 和页面名不同
    dblp_abbr: ipdps
  - id: IEEE-TC
    dblp_key: journals/tc        # 期刊（自动从 index 解析 volume）
date_range:
  start: 2022
  end: 2026
```

### topic-cpu-ai.yaml

```yaml
topic: "CPU AI acceleration"
keywords:
  - term: "AMX"
    weight: 10          # 核心关键词，高分
  - term: "tensor"
    weight: 3
  - term: "AI"
    weight: 1           # 通用词，低分扩大召回
```

**打分阈值：** High(>=10) / Medium(>=5) / Low(>=1) / None(0)

## Web 审阅工具

`review_server.py` + `review.html` 提供本地 Web 审阅界面：

- **2x2 网格**：同时展示 4 篇论文
- **关键词金色高亮**：按权重从暗到亮金色渐变
- **自定义标签**：keep / core / related / skip + 自由输入
- **键盘快捷键**：`1234`=keep, `qwer`=skip, `←→`=翻页, `Ctrl+S`=保存
- **持久化**：标记写回 CSV 的 keep/notes 列

## 进一步阅读

- 时间线：[timeline.md](timeline.md)
- 总体方案：[plan/README.md](plan/README.md)
- 旧版文档：[doc/survey-crawler.md](doc/survey-crawler.md)
