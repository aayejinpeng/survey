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
| 6 | `corpus_reviewer.py` | ✅ | Corpus 对照审阅 + 人工修订 |
| 7 | `build_graph.py` | ⬜ | 引用图可视化 |

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
│       ├── doi-list.txt         # keep 论文的 DOI 列表
│       └── corpus/              # LLM 分析语料
│           ├── draft/           # GLM 原始提取
│           ├── llm/
│           │   ├── glm5.1/      # GLM 提取结果 *.json
│           │   └── gpt5.4/      # GPT 审查 + 修正
│           └── human_review/    # 人工编辑保存
├── pdfs/                        # PDF 下载目录
│   └── cpu-ai/                  # CPU AI 主题的 PDF 文件
├── corpus_reviewer.py            # Step 6: Corpus 对照审阅 Web 服务
├── tools/
│   └── s2_fetch.py              # S2 batch API 客户端
├── skill/
│   ├── claude/
│   │   └── analyze-paper-claude.md  # Claude Code skill: 论文分析
│   └── codex/
│       └── paper-json-review/       # Codex skill: LLM 语料审查
├── fetch_dblp.py                # Step 1: DBLP 抓取
├── enrich_papers.py             # Step 2: S2/Crossref/arXiv 富化
├── score_papers.py              # Step 3: 关键词打分
├── slice_csv.py                 # Step 3.5: CSV 截取
├── review_server.py             # Step 4: Web 审阅服务端
├── review.html                  # Step 4: Web 审阅前端
├── sync_zotero.py               # Step 5: Zotero PDF 同步
├── export_dois.py               # Step 5 备选: 导出 DOI 链接手动下载
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

# Step 5: 从 Zotero 同步 PDF（需要本地 Zotero 运行）
python3 sync_zotero.py \
    --input data/topics/cpu-ai/scored-score-gte11.csv \
    --output-dir pdfs/cpu-ai/

# Step 5 替代方案：导出 DOI 链接手动下载（Zotero 不可用时）
python3 export_dois.py \
    --input data/topics/cpu-ai/scored-score-gte11.csv \
    --output pdfs/cpu-ai/doi-list.txt

# Step 6: 启动 Corpus 对照审阅（浏览器打开 http://localhost:5000）
python3 corpus_reviewer.py --topic cpu-ai
# 或指定其他 topic / port
python3 corpus_reviewer.py --topic another-topic --port 8080
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
      ↓
server.py → Corpus 对照审阅 + 人工修订 (http://localhost:5000)
```

`--topic` 参数对应 `data/topics/` 下的子目录名，同时关联 `pdfs/{topic}/` 下的 PDF 文件。
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

## Corpus 对照审阅工具

`corpus_reviewer.py` 提供左右分栏的 Web 界面，用于对照查看 LLM 分析语料和原始 PDF，并支持人工修订。

### 启动

```bash
pip install flask
python3 corpus_reviewer.py --topic <topic-name>
```

`--topic` 指定 `data/topics/` 下的主题目录名（默认 `cpu-ai`），服务器会读取对应的 `corpus/llm/` 语料和 `pdfs/<topic>/` 下的 PDF。`--port` 可指定端口（默认 5000）。

### 布局

左半边为结构化 JSON 展示 / 编辑区，右半边为 PDF 阅读器。

### 四个视图

按 `↑` `↓` 或 `1` `2` `3` `4` 切换：

| 视图 | 数据源 | 说明 |
|------|--------|------|
| **GPT Review** | `corpus/llm/gpt5.4/*.review.json` | GPT 对 GLM 提取结果的审查（verdict、checks、field reviews、issues） |
| **GLM Extraction** | `corpus/llm/glm5.1/*.json` | GLM 对论文的原始提取（paper info、abstract、metadata） |
| **GPT Revised** | `corpus/llm/gpt5.4/*.revised.json` | GPT 修正后的结构化分析（research、contributions、gaps） |
| **Human Edit** | 基于 GPT Revised，保存到 `corpus/human_review/` | 可编辑表单，直接在 GPT 结果上修改并保存 |

### 快捷键

| 按键 | 功能 |
|------|------|
| `←` `→` | 切换上/下一篇论文 |
| `↑` `↓` | 切换视图（循环） |
| `1` `2` `3` `4` | 直接跳到对应视图 |
| `Ctrl+S` | 在 Human Edit 视图中保存 |

编辑框内输入时方向键和数字键不触发导航。顶栏显示 saved/unsaved 状态。

## Skill 目录

`skill/` 存放 LLM 辅助工具的 skill 定义，用于论文分析和语料审查。

### Claude Code Skill: Analyze Paper

| 文件 | 说明 |
|------|------|
| `skill/claude/analyze-paper-claude.md` | 论文第一轮分析 |

通过 Claude Code CLI 调用，读取论文的 `abstract` 和 `body_text`，生成结构化 dossier JSON（研究目的、贡献、主题分类、技术细节和 proposal 论据），用于 proposal writing。

### Codex Skill: Paper JSON Review

| 文件 | 说明 |
|------|------|
| `skill/codex/paper-json-review/SKILL.md` | Skill 入口定义 |
| `skill/codex/paper-json-review/references/analysis-contract.md` | Dossier 输出格式约定 |
| `skill/codex/paper-json-review/references/review-schema.md` | Review 输出格式约定 |
| `skill/codex/paper-json-review/references/review-output.schema.json` | JSON Schema |
| `skill/codex/paper-json-review/scripts/preflight_review.py` | 确定性预检脚本 |
| `skill/codex/paper-json-review/scripts/run_codex_review.sh` | 一键审查入口 |

**功能**：对 LLM 生成的论文 dossier 进行第二轮审查，验证结构合规性、引文准确性、语义可信度，输出 review JSON 和 corrected revised JSON。

**使用流程**：

1. 安装 skill 到 `$CODEX_HOME/skills/`：
   ```bash
   bash skill/codex/paper-json-review/scripts/install_workspace_codex_home.sh
   ```

2. 通过 Codex CLI 调用：
   ```bash
   bash skill/codex/paper-json-review/scripts/run_codex_review.sh \
       <path-to-dossier-json>
   ```

3. 或单独运行预检脚本：
   ```bash
   python skill/codex/paper-json-review/scripts/preflight_review.py \
       --analysis-json <dossier.json> \
       --paper-json <paper.json> \
       --pretty
   ```

**输出**：包含 `review`（结构化审查报告）和 `revised_analysis`（修正后的 dossier）的 JSON，保存到 `corpus/llm/gpt5.4/` 下。

## Corpus Reviewer API

| 路由 | 方法 | 说明 |
|------|------|------|
| `/api/papers` | GET | 论文列表（含各模型的可用文件） |
| `/api/json/<model>/<file>` | GET | 获取 LLM 生成的 JSON |
| `/api/human/<basename>` | GET | 获取人工编辑的 JSON（无则返回 null） |
| `/api/human/<basename>` | PUT | 保存人工编辑的 JSON |
| `/pdf/<filename>` | GET | 获取 PDF 文件 |

## 进一步阅读

- 时间线：[timeline.md](timeline.md)
- 总体方案：[plan/README.md](plan/README.md)
- 详细文档：[doc/README.md](doc/README.md)
- 旧版文档：[doc/survey-crawler.md](doc/survey-crawler.md)
