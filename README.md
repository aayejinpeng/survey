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
| 6 | `extract_papers.py` | ✅ | `corpus/draft/*.json` |
| 7 | `paper_review_pipeline.py` | ✅ | `corpus/llm/{glm5.1,gpt5.4}/*.json` |
| 8 | `corpus_reviewer.py` | ✅ | Corpus 对照审阅 + 人工修订 |
| 9 | `build_graph.py` | ⬜ | 引用图可视化 |

## 当前数据（2026-04-10）

- **14,600 篇论文**，103 个 venue×year CSV
- **27 个会议** + **7 个期刊**，覆盖 2022-2026
- **摘要覆盖率 92%**
- CPU AI 主题：score >= 11 共 196 篇，12 篇已标记 keep
- **Corpus 状态**：draft 语料已生成，pipeline 正在运行中

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
│           ├── draft/           # Step 6: PDF 解析后的 draft JSON
│           ├── llm/
│           │   ├── glm5.1/      # Step 7a: GLM 提取结果 *.json
│           │   └── gpt5.4/      # Step 7b: GPT 审查 + 修正
│           ├── human_review/    # Step 8: 人工编辑保存
│           └── paper_review_pipeline/  # Pipeline 日志和状态
├── pdfs/                        # PDF 下载目录
│   └── cpu-ai/                  # CPU AI 主题的 PDF 文件
├── extract_papers.py            # Step 6: PDF 解析为 draft JSON
├── paper_review_pipeline.py     # Step 7: 双模型对抗生成 pipeline
├── corpus_reviewer.py            # Step 8: Corpus 对照审阅 Web 服务
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

# Step 6: 从 PDF 生成 draft corpus JSON
python3 extract_papers.py \
    pdfs/cpu-ai/ \
    data/topics/cpu-ai/scored-score-gte11.csv \
    -o data/topics/cpu-ai/corpus/draft/

# Step 7: 运行双模型对抗生成 pipeline
python3 paper_review_pipeline.py --topic cpu-ai --limit 10

# Step 8: 启动 Corpus 对照审阅（浏览器打开 http://localhost:5000）
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
extract_papers.py → corpus/draft/*.json  (PDF 解析 + CSV 元数据)
      ↓
paper_review_pipeline.py → corpus/llm/{glm5.1,gpt5.4}/*.json
                           (双模型对抗生成：GLM 提取 → GPT 审查)
      ↓
corpus_reviewer.py → Corpus 对照审阅 + 人工修订 (http://localhost:5000)
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

`corpus_reviewer.py` 提供左右分栏的 Web 界面，用于对照查看 LLM 分析语料和原始 PDF，并支持人工修订。这是 Step 8 的核心工具。

### 启动

```bash
pip install flask
python3 corpus_reviewer.py --topic <topic-name>
```

`--topic` 指定 `data/topics/` 下的主题目录名（默认 `cpu-ai`），服务器会读取对应的 `corpus/llm/` 语料和 `pdfs/<topic>/` 下的 PDF。`--port` 可指定端口（默认 5000）。

### 布局

- **左半边**：结构化 JSON 展示 / 编辑区
- **右半边**：PDF 阅读器

### 四个视图

按 `↑` `↓` 或 `1` `2` `3` `4` 切换：

| 视图 | 数据源 | 说明 |
|------|--------|------|
| **GPT Review** | `corpus/llm/gpt5.4/*.review.json` | GPT 对 GLM 提取结果的审查（verdict、checks、field reviews、issues） |
| **GLM Extraction** | `corpus/llm/glm5.1/*.json` | GLM 对论文的原始提取（paper info、abstract、metadata） |
| **GPT Revised** | `corpus/llm/gpt5.4/*.revised.json` | GPT 修正后的结构化分析（research、contributions、gaps） |
| **Human Edit** | 基于 GPT Revised，保存到 `corpus/human_review/` | 可编辑表单，直接在 GPT 结果上修改并保存 |

### 人工编辑工作流

1. 先查看 **GPT Review** 了解审查意见和问题
2. 参考 **GLM Extraction** 查看原始提取
3. 查看 **GPT Revised** 获取修正后的版本
4. 在 **Human Edit** 中进行最终编辑并保存

### 快捷键

| 按键 | 功能 |
|------|------|
| `←` `→` | 切换上/下一篇论文 |
| `↑` `↓` | 切换视图（循环） |
| `1` `2` `3` `4` | 直接跳到对应视图 |
| `Ctrl+S` | 在 Human Edit 视图中保存 |

编辑框内输入时方向键和数字键不触发导航。顶栏显示 saved/unsaved 状态。

## Step 6: extract_papers.py — PDF 解析与 Draft Corpus 生成

### 功能

从 PDF 文件提取正文文本，并结合 CSV 中的元数据生成 draft corpus JSON。

### 特性

- **正文提取**：使用 PyMuPDF (fitz) 或 pdfplumber 提取 PDF 正文，在 References 章节停止
- **噪声清理**：自动移除页眉、页脚、版权声明、DOI 行等噪声
- **元数据合并**：从 CSV 中读取 title、authors、year、venue、doi、abstract、citation_count 等元数据
- **批量处理**：支持批量处理整个 PDF 目录，输出为单独的 JSON 文件

### 使用方式

```bash
python3 extract_papers.py \
    pdfs/cpu-ai/ \
    data/topics/cpu-ai/scored-score-gte11.csv \
    -o data/topics/cpu-ai/corpus/draft/
```

### 输出格式

每个 PDF 生成一个 JSON 文件：

```json
{
  "file": "A-Heterogeneous-CNN-Compilation-Framework-for-RISC-V-CPU-and-NPU-Integration-Bas.pdf",
  "title": "A Heterogeneous CNN Compilation Framework for RISC-V CPU and NPU Integration",
  "authors": "Author1, Author2",
  "year": 2024,
  "venue": "Conference Name",
  "doi": "10.xxx/xxxx",
  "url": "https://...",
  "abstract": "摘要内容",
  "citation_count": "10",
  "relevance_score": "15",
  "relevance": "High",
  "matched_keywords": "RISC-V, CNN, NPU",
  "body_text": "从 PDF 提取的正文内容...",
  "text_length": 15000,
  "csv_matched": true,
  "extraction_status": "success"
}
```

### 为什么需要结构化的 Draft

1. **标准化输入**：为后续的 LLM 分析提供统一的数据格式
2. **元数据丰富**：CSV 中的结构化元数据（引用数、相关性评分）帮助 LLM 理解论文重要性
3. **正文干净**：经过噪声清理的正文文本，减少 LLM 处理的干扰
4. **可追溯**：保留提取状态（success/failed），便于问题排查

## Step 7: paper_review_pipeline.py — 双模型对抗生成

### 功能

异步生产者-消费者 pipeline，自动完成 Claude 分析和 Codex 审查两阶段处理。

### 架构设计

```
┌─────────────────────────────────────────────────────────────┐
│                    paper_review_pipeline.py                 │
├─────────────────────────────────────────────────────────────┤
│                                                             │
│  ┌──────────────────┐         ┌──────────────────┐          │
│  │   Producer       │         │   Consumer       │          │
│  │   (Claude)       │   ──→   │   (Codex)        │          │
│  │                  │  Queue  │                  │          │
│  │  • 读取 draft     │         │  • 读取 analysis │          │
│  │  • 调用 Claude    │         │  • 调用 Codex    │          │
│  │  • 保存 GLM       │         │  • 保存 review   │          │
│  │    analysis.json │         │   + revised.json │          │
│  └──────────────────┘         └──────────────────┘          │
│         ↓                            ↓                      │
│  corpus/llm/glm5.1/           corpus/llm/gpt5.4/            │
└─────────────────────────────────────────────────────────────┘
```

### 使用方式

```bash
# 基本用法：处理整个 corpus
python3 paper_review_pipeline.py --topic cpu-ai

# 限制处理数量
python3 paper_review_pipeline.py --topic cpu-ai --limit 10

# 指定特定论文
python3 paper_review_pipeline.py --topic cpu-ai \
    --papers data/topics/cpu-ai/corpus/draft/paper1.json \
            data/topics/cpu-ai/corpus/draft/paper2.json

# 重试失败的论文
python3 paper_review_pipeline.py --topic cpu-ai \
    --retry-failed-from runs/latest/summary.json

# 严格串行模式（无 pipeline 重叠）
python3 paper_review_pipeline.py --topic cpu-ai --strict-serial

# Dry run（仅打印命令，不执行）
python3 paper_review_pipeline.py --topic cpu-ai --dry-run
```

### 关键参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--topic` | 主题目录名 | `cpu-ai` |
| `--limit` | 处理论文数量限制 | `null` (全部) |
| `--papers` | 显式指定论文 JSON 路径 | - |
| `--queue-size` | Pipeline 队列大小 | 1 |
| `--strict-serial` | 禁用 pipeline 重叠 | `false` |
| `--skip-existing` | 跳过已存在的结果 | `false` |
| `--dry-run` | 仅打印命令不执行 | `false` |
| `--retry-failed-from` | 从之前的失败记录重试 | - |
| `--claude-timeout-sec` | Claude 超时时间 | 1800 |
| `--codex-timeout-sec` | Codex 超时时间 | 3600 |

### 输出结构

```
corpus/
├── paper_review_pipeline/
│   ├── claude/
│   │   ├── {stem}.cmd.txt       # 命令行
│   │   ├── {stem}.stdout.log    # 标准输出
│   │   └── {stem}.stderr.log    # 错误输出
│   ├── codex/
│   │   ├── {stem}.cmd.txt
│   │   ├── {stem}.stdout.log
│   │   └── {stem}.stderr.log
│   ├── status/
│   │   ├── {stem}.claude.status.json  # 实时状态
│   │   └── {stem}.codex.status.json
│   └── runs/
│       └── latest/
│           ├── summary.json           # 运行摘要
│           ├── failed_papers.json     # 失败论文列表
│           └── failed_papers.txt      # 失败论文列表（纯文本）
└── llm/
    ├── glm5.1/
    │   └── {stem}.json           # Claude 生成
    └── gpt5.4/
        ├── {stem}.review.json     # Codex 审查
        └── {stem}.revised.json    # Codex 修正
```

### 为什么使用双模型对抗生成

1. **降低幻觉风险**：第一个模型（Claude）负责生成，第二个模型（GPT）负责审查
2. **专业性互补**：Claude 擅长长文本分析和结构化输出，GPT 擅长审查和修正
3. **可追溯性**：保留原始生成、审查意见和修正版本，便于人工审核
4. **质量保证**：通过结构化的审查格式，强制第二个模型检查特定维度

### 容错与重试

Pipeline 具备完善的容错机制：

- **自动重试**：对可重试错误（rate limit、timeout）自动重试
- **失败分类**：区分可重试失败和致命失败
- **连续失败保护**：Codex 连续 N 次失败后自动停止
- **状态持久化**：每个任务的状态实时写入 JSON，可断点续传

### 阶段状态文件示例

```json
{
  "stage": "claude",
  "job_name": "paper.json",
  "state": "running",
  "pid": 12345,
  "started_at_unix": 1712746800,
  "elapsed_sec": 45.2,
  "timeout_sec": 1800,
  "cwd": "/root/opencute",
  "command": ["claude", "-p", "/analyze-paper-claude ..."]
}
```

## 结构化数据约束与人工干预

### 为什么使用结构化数据

1. **可验证性**：JSON Schema 可以自动验证格式，避免无效输出
2. **可解析性**：程序可以直接读取和处理，无需二次解析
3. **可追溯性**：每个字段都有明确的来源和含义
4. **可扩展性**：可以灵活添加新字段而不破坏现有流程

### 结构化约束的实施

1. **输入约束**（draft JSON）
   - 固定的字段名和类型
   - 必填字段验证
   - 枚举值约束（如 theme_primary、workstream_fit）

2. **输出约束**（analysis JSON）
   - JSON Schema 定义
   - 字段长度限制
   - 引文格式要求

3. **审查约束**（review JSON）
   - 预定义的检查项
   - 标准化的严重程度分级
   - 结构化的问题报告

### 关键节点的人工干预

1. **Web 审阅**（Step 4）
   - 人工筛选高相关论文
   - 标记核心论文、相关论文
   - 添加个人笔记

2. **Corpus 对照审阅**（Step 8）
   - 查看 LLM 分析与原文的对照
   - 修正错误的提取
   - 补充遗漏的要点
   - 标记不确定的内容

3. **预检脚本**
   - 自动检查结构合规性
   - 验证引文存在性
   - 检查枚举值有效性

### 人工干预的价值

1. **质量把关**：LLM 可能产生幻觉或过度推断
2. **领域知识**：人工可以识别 LLM 无法理解的技术细节
3. **上下文理解**：人工可以结合研究目标判断相关性
4. **责任归属**：关键决策需要人工确认

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
