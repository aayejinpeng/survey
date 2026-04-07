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

## 实施步骤

### Step 3.1: 读取 filtered CSV

- 解析 CSV，加载 paper_id, title, year, citation_count, venue 等字段
- 构建 paper_id → paper_info 映射

### Step 3.2: S2 引用关系获取

- 对每篇论文调用 S2 API：
  - `GET /paper/{id}/references?fields=paperId,title,year,citationCount,externalIds`
  - `GET /paper/{id}/citations?fields=paperId,title,year,citationCount,externalIds`
- 只保留与 filtered 集合内论文的引用关系（max-depth=1）
- 结果缓存到 `citation-cache.json`（避免重复请求）

复用已有 S2 工具的 `_request_json` 和 `_headers`：
```python
TOOLS_DIR = os.path.join(os.path.dirname(__file__), '..',
    'sleep-work-agent/Auto-claude-code-research-in-sleep/tools')
sys.path.insert(0, TOOLS_DIR)
from semantic_scholar_fetch import _request_json, _headers
```

### Step 3.3: 构建 networkx 有向图

- 节点：每篇 filtered 论文
- 边：A → B 表示 A 引用了 B
- 节点属性：title, year, citation_count, venue

### Step 3.4: matplotlib 渲染

- 布局：spring_layout（<30 节点）或 kamada_kawai_layout
- 节点大小：∝ log(citation_count + 1)
- 节点颜色：按年份渐变（旧→蓝，新→红）
- 标签：截断标题（前 40 字符）+ 年份
- 保存 PNG

### Step 3.5: DOT 文件输出

- 遍历 networkx 图，生成 Graphviz DOT 格式
- DOT 可用在线工具渲染（dreampuf.github.io/GraphvizOnline）
- 也可本地 `dot -Tsvg` 渲染

### Step 3.6: 统计摘要

- 输出 `citation-graph-stats.md`：
  - 总节点数、边数
  - 最高 in-degree（集合内最被引）
  - 最高 out-degree（引用最多）
  - PageRank top 5
  - 连通分量数及大小

### Step 3.7: survey-graph.md Skill

- 运行 `citation_graph.py`
- 展示统计摘要
- 提供 DOT/PNG 文件路径
- 后续升级：加 `--format pyvis` 生成交互式 HTML

## 依赖

- networkx（已安装）
- matplotlib（已安装）
- semantic_scholar_fetch.py（import _request_json, _headers）

## 验证

1. 准备一个小的 filtered CSV（5-10 篇论文）
2. 运行 `citation_graph.py build`
3. 检查 PNG 可读、DOT 格式正确、stats.md 合理
4. 运行 `/survey-graph "test"` 确认 skill 串联正确

## 预估代码量

- citation_graph.py: ~250-300 行 Python
- survey-graph.md: ~50 行 markdown
