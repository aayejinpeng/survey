# Step 8: corpus_reviewer.py — Corpus 对照审阅与人工修订

## 状态

✅ 已实现。

## 目标

提供 Web 界面，允许研究人员对照查看：
1. 原始 PDF 论文
2. GLM 提取的原始分析
3. GPT 的审查意见
4. GPT 修正后的版本

并支持在 GPT 修正版本基础上进行人工编辑和保存。

## 常用命令

```bash
# 启动审阅服务
python3 corpus_reviewer.py --topic cpu-ai

# 指定端口
python3 corpus_reviewer.py --topic cpu-ai --port 8080

# 浏览器访问
# http://localhost:5000
```

## 当前支持参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--topic` | 主题目录名（`data/topics/` 下） | `cpu-ai` |
| `--port` | 服务端口 | 5000 |

## 功能特性

### 1. 四视图对照

| 视图 | 快捷键 | 数据源 | 说明 |
|------|--------|--------|------|
| **GPT Review** | `1` | `corpus/llm/gpt5.4/*.review.json` | GPT 对 GLM 提取结果的审查（verdict、checks、field reviews、issues） |
| **GLM Extraction** | `2` | `corpus/llm/glm5.1/*.json` | GLM 对论文的原始提取（paper info、abstract、metadata） |
| **GPT Revised** | `3` | `corpus/llm/gpt5.4/*.revised.json` | GPT 修正后的结构化分析（research、contributions、gaps） |
| **Human Edit** | `4` | `corpus/human_review/*.json` | 可编辑表单，直接在 GPT 结果上修改并保存 |

### 2. 左右分栏布局

- **左半边**：结构化 JSON 展示 / 编辑区
- **右半边**：PDF 阅读器（嵌入 iframe）

### 3. 人工编辑功能

在 **Human Edit** 视图中可以编辑：

#### 基本信息字段

- 标题、作者、年份、会议、DOI、URL
- 主题分类（theme_primary、theme_secondary）
- 工作流分类（workstream_fit）
- 研究目的、意义、关键技术、关键结果
- 是否为 CUTE 基线（is_close_baseline_to_cute）

#### 数组字段（可动态增删）

- **Contributions**：贡献点（point + evidence）
- **Gaps**：研究空白（gap + evidence + relevance_to_cute）

#### 对象字段

- **Proposal Evidence**：提案论据（多个文本字段）

### 4. 快捷键

| 按键 | 功能 |
|------|------|
| `←` `→` | 切换上/下一篇论文 |
| `↑` `↓` | 切换视图（循环） |
| `1` `2` `3` `4` | 直接跳到对应视图 |
| `Ctrl+S` | 在 Human Edit 视图中保存 |

**注意**：编辑框内输入时方向键和数字键不触发导航。

## API 端点

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/papers` | GET | 论文列表（含各模型的可用文件） |
| `/api/json/<model>/<file>` | GET | 获取 LLM 生成的 JSON |
| `/api/human/<basename>` | GET | 获取人工编辑的 JSON（无则返回 null） |
| `/api/human/<basename>` | PUT | 保存人工编辑的 JSON |
| `/pdf/<filename>` | GET | 获取 PDF 文件 |

## 目录结构

```
data/topics/{topic}/
├── corpus/
│   ├── draft/                    # Step 6: PDF 解析
│   │   ├── {stem}.json
│   │   └── index.json
│   ├── llm/                      # Step 7: 双模型生成
│   │   ├── glm5.1/
│   │   │   └── {stem}.json
│   │   └── gpt5.4/
│   │       ├── {stem}.review.json
│   │       └── {stem}.revised.json
│   └── human_review/             # Step 8: 人工修订
│       └── {stem}.json           # 人工最终修订版本
└── scored-score-gte11.csv        # Step 3.5: 筛选后的论文列表
```

## 人工编辑工作流

### 推荐审阅流程

```
1. 查看 GPT Review (View 1)
   了解审查意见和发现的问题

   ↓

2. 参考 GLM Extraction (View 2)
   查看 Claude 的原始提取结果

   ↓

3. 查看 GPT Revised (View 3)
   获取 GPT 修正后的版本

   ↓

4. 在 Human Edit (View 4) 中编辑
   - 以 GPT Revised 为基础
   - 根据对照结果进行修正
   - 保存最终版本
```

### 典型修正场景

1. **引文错误**：回到 View 2 查找正确的原文引用
2. **过度推断**：根据 View 1 的审查意见，删除不支持的结论
3. **主题分类**：根据研究内容调整 theme_primary/workstream_fit
4. **证据补充**：从 PDF 中找到被遗漏的重要证据

## UI 特性

### 1. 顶部信息栏

- **论文名称**：当前论文的标准化名称
- **计数器**：显示进度（如 "3 / 196"）
- **保存状态**：显示 saved/unsaved 徽章

### 2. 视图标签栏

- 四个视图按钮，带快捷键提示
- 当前视图高亮显示
- 右侧显示快捷键帮助

### 3. JSON 展示面板

#### GPT Review 视图

- **Verdict**：总体评估（pass/minor_revision/major_revision/reject）
- **Checks**：结构化检查项网格
- **Field Reviews**：各字段审查详情
- **Issues**：发现的问题列表

#### GLM Extraction 视图

- **Paper Info**：元数据
- **Abstract**：摘要
- **Metadata**：提取状态、文本长度等

#### GPT Revised 视图

- **Paper Info**：论文基本信息
- **Research**：研究目的、意义、技术、结果
- **Contributions**：贡献点列表
- **Gaps**：研究空白列表
- **Proposal Evidence**：提案论据

#### Human Edit 视图

- **可编辑表单**：所有字段可编辑
- **动态数组**：可添加/删除贡献点和空白
- **保存按钮**：Ctrl+S 或点击保存按钮

## 输出格式

### 人工编辑 JSON

```json
{
  "title": "论文标题",
  "authors": "作者列表",
  "year": 2024,
  "venue": "会议名称",
  "doi": "10.xxx/xxxx",
  "url": "https://...",
  "theme_primary": "1. CPU-side AI acceleration",
  "theme_secondary": null,
  "workstream_fit": "1",
  "is_close_baseline_to_cute": false,
  "research_purpose": "研究目的（中文）",
  "research_significance": "研究意义（中文）",
  "key_technique": "关键技术（中文）",
  "key_results": "关键结果（中文）",
  "contributions": [
    {
      "point": "贡献点（中文）",
      "evidence": "原文证据（英文）"
    }
  ],
  "gap_identified": [
    {
      "gap": "研究空白（中文）",
      "evidence": "原文证据（英文）",
      "relevance_to_cute": "与 CUTE 的关联（中文）"
    }
  ],
  "proposal_evidence": {
    "for_state_of_art": "国内外研究现状论据（中文）",
    "for_gap": "研究空白论据（中文）",
    "for_feasibility": "可行性论据（中文）"
  }
}
```

## 用户工作流

```
paper_review_pipeline.py → corpus/llm/{glm5.1,gpt5.4}/*.json
      ↓
corpus_reviewer.py → 启动 Web 服务
      ↓
浏览器对照审阅 → 人工编辑 → 保存
      ↓
corpus/human_review/*.json → 最终版本
```

## 注意事项

1. **自动保存**：仅通过 Ctrl+S 或点击保存按钮手动保存
2. **状态提示**：unsaved 状态切换论文时会提示保存
3. **版本管理**：human_review 版本会覆盖之前的版本
4. **数据来源**：Human Edit 以 GPT Revised 为基础，如无则无法编辑

## 质量保证

### 审查检查清单

- [ ] 所有英文证据都存在于原文中
- [ ] 中文总结准确反映原文内容
- [ ] 数值、性能数据准确无误
- [ ] 主题分类与内容相符
- [ ] 贡献点有明确证据支持
- [ ] 研究空白确实来自论文
- [ ] Proposal 论据不过度推断

### 常见问题处理

| 问题 | 处理方法 |
|------|----------|
| 英文证据不存在 | 从 View 2 的 GLM Extraction 或 PDF 中查找正确引用 |
| 中文总结不准确 | 参考 PDF 原文，重新撰写 |
| 数值错误 | 查看实验结果部分，确认正确数值 |
| 分类错误 | 根据论文实际内容调整 theme/workstream |
| 缺少贡献点 | 从 PDF 的 contribution 部分补充 |
| 研究空白推断 | 删除无证据支持的空白，保留论文明确提到的 |

## 扩展性

### 添加新的视图

修改 `VIEWS` 数组和渲染函数：

```javascript
const VIEWS=['review','raw','revised','human','custom'];
```

### 自定义字段

在 `renderEditForm()` 中添加新的编辑字段。

### 集成外部工具

通过 API 端点可以集成其他工具分析结果。

## 故障排除

### PDF 无法显示

- 检查 PDF 文件是否存在
- 确认浏览器支持 PDF 嵌入
- 尝试直接访问 PDF URL

### JSON 加载失败

- 检查文件路径是否正确
- 确认 JSON 格式是否有效
- 查看浏览器控制台错误

### 保存失败

- 检查 `corpus/human_review/` 目录权限
- 确认服务器正在运行
- 查看服务器日志

## 与上游下游集成

- **上游**：读取 `paper_review_pipeline.py` 生成的 glm5.1 和 gpt5.4 数据
- **下游**：输出的 `human_review/` 数据可用于最终的分析报告或 proposal 写作

## 设计理念

### 为什么需要人工审阅？

1. **质量把关**：LLM 可能产生幻觉或过度推断
2. **领域知识**：人工可以识别 LLM 无法理解的技术细节
3. **上下文理解**：人工可以结合研究目标判断相关性
4. **责任归属**：关键决策需要人工确认

### UI 设计原则

1. **对照效率**：左右分栏，同时查看 PDF 和分析
2. **快速切换**：四个视图一键切换，快捷键支持
3. **状态可见**：保存状态、进度清晰可见
4. **编辑友好**：表单验证、自动保存提示
