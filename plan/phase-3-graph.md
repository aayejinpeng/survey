# Phase 3: citation_graph.py — 引用图谱

## 目标

实现 `citation_graph.py`，从 filtered CSV 构建引用关系图谱并可视化。

## 文件

- `workspace/survey/citation_graph.py`
- `.claude/commands/survey/survey-graph.md`

## CLI 接口

```bash
python3 citation_graph.py build \
    --input .claude/survey-data/{topic}/abstracts-filtered.csv \
    --output-dir .claude/survey-data/{topic}/ \
    --format png,dot \
    --max-depth 1
```

## 数据前提

输入 CSV 至少包含以下列：

- `paper_id`
- `arxiv_id`
- `s2_paper_id`
- `title`
- `year`
- `citation_count`
- `venue`

其中：

- `paper_id` 只用于集合内主键和展示
- `s2_paper_id` 才是图谱阶段调用 S2 API 的首选 ID
- 只有 `arxiv_id` 的行，需要先 resolve 成 `s2_paper_id`

## 实施步骤

### Step 3.1: 读取 filtered CSV

- 解析 CSV，加载 `paper_id`、`arxiv_id`、`s2_paper_id`、`title`、`year`、`citation_count`、`venue`
- 构建：
  - `paper_id -> paper_info`
  - `s2_paper_id -> paper_id`
  - `arxiv_id -> paper_id`

### Step 3.2: S2 ID resolve + 引用关系获取

- 预加载 `citation-cache.json`
- cache 建议至少包含两类信息：
  - `resolved_ids`: `arxiv_id -> s2_paper_id`
  - `edges`: `s2_paper_id -> {references, citations}`
- 对每篇论文：
  - 如果已有 `s2_paper_id`，直接使用
  - 如果只有 `arxiv_id`，先调用 `get_paper("ARXIV:{arxiv_id}")` resolve 并缓存
  - 如果两者都没有，标记为 unresolved，后续统计中展示
- 对可解析的每篇论文调用 S2 API：
  - `GET /paper/{s2_paper_id}/references?fields=paperId,title,year,citationCount,externalIds`
  - `GET /paper/{s2_paper_id}/citations?fields=paperId,title,year,citationCount,externalIds`
- 只保留与 filtered 集合内论文的引用关系（`max-depth=1`）

复用已有 S2 工具：
```python
TOOLS_DIR = os.path.join(
    os.path.dirname(__file__),
    "..",
    "sleep-work-agent/Auto-claude-code-research-in-sleep/tools",
)
sys.path.insert(0, TOOLS_DIR)
from semantic_scholar_fetch import _headers, _request_json, get_paper
```

### Step 3.3: 构建 networkx 有向图

- 节点：每篇 filtered 论文
- 边：`A -> B` 表示 `A` 引用了 `B`
- 节点属性：
  - `title`
  - `year`
  - `citation_count`
  - `venue`
  - `paper_id`

### Step 3.4: matplotlib 渲染

- 布局：`spring_layout`（<30 节点）或 `kamada_kawai_layout`
- 节点大小：`log(citation_count + 1)` 比例缩放
- 节点颜色：按年份渐变（旧 -> 蓝，新 -> 红）
- 标签：截断标题（前 40 字符）+ 年份
- 保存 PNG

### Step 3.5: DOT 文件输出

- 遍历 networkx 图，生成 Graphviz DOT
- DOT 可用在线工具渲染，也可本地 `dot -Tsvg` 转换

### Step 3.6: 统计摘要

- 输出 `citation-graph-stats.md`
- 至少包含：
  - 总节点数、边数
  - unresolved 节点数
  - 最高 in-degree（集合内最被引）
  - 最高 out-degree（引用最多）
  - PageRank top 5
  - 连通分量数及大小

### Step 3.7: survey-graph.md Skill

- 运行 `citation_graph.py`
- 展示统计摘要
- 提供 DOT / PNG 文件路径
- 如果有 unresolved 论文，在 skill 输出里明确列出数量
- 后续升级：加 `--format pyvis` 生成交互式 HTML

## 依赖

- `networkx`
- `matplotlib`
- `semantic_scholar_fetch.py`

## 验证

1. 准备一个 mixed-ID `abstracts-filtered.csv`（同时包含仅 arXiv 行和带 `s2_paper_id` 行）。
2. 运行 `citation_graph.py build`。
3. 检查：
   - PNG 可读
   - DOT 格式正确
   - `stats.md` 含 unresolved 统计
4. 在同一输入上第二次运行，确认 cache 生效、请求量下降。
5. 运行 `/survey-graph "test"`，确认 skill 串联正确。

## 预估代码量

- `citation_graph.py`: ~280-360 行 Python
- `survey-graph.md`: ~50-70 行 markdown
