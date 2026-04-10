# 设计文档：结构化数据约束与人工干预

## 概述

本文档说明 Survey Pipeline 中使用结构化数据约束 LLM 输入输出的设计理念，以及在关键节点进行人工干预的策略。

## 目录

1. [为什么需要结构化数据](#为什么需要结构化数据)
2. [结构化约束的实施](#结构化约束的实施)
3. [关键节点的人工干预](#关键节点的人工干预)
4. [结构化与人工干预的协同](#结构化与人工干预的协同)

---

## 为什么需要结构化数据

### 1. 可验证性

结构化数据（JSON）可以通过 JSON Schema 自动验证：

```json
{
  "type": "object",
  "required": ["title", "authors", "year", "research_purpose"],
  "properties": {
    "research_purpose": {"type": "string", "minLength": 10},
    "year": {"type": "integer", "minimum": 2020, "maximum": 2030}
  }
}
```

**好处**：
- 自动检测缺失字段
- 验证数据类型正确性
- 强制执行最小长度等约束

### 2. 可解析性

程序可以直接读取和处理，无需复杂的文本解析：

```python
# 读取研究目的
purpose = dossier["research_purpose"]

# 提取所有贡献点
contributions = [c["point"] for c in dossier["contributions"]]

# 检查是否为 CUTE 基线
is_baseline = dossier.get("is_close_baseline_to_cute", False)
```

### 3. 可追溯性

每个字段都有明确的来源和含义：

| 字段 | 来源 | 说明 |
|------|------|------|
| `title` | CSV 元数据 | 论文标题，来自 DBLP |
| `abstract` | CSV 元数据 | 摘要，来自 S2/Crossref |
| `body_text` | PDF 提取 | 正文文本，extract_papers.py 提取 |
| `research_purpose` | Claude 生成 | LLM 分析结果 |
| `contributions` | Claude 生成 | 结构化提取，含 evidence 字段 |

### 4. 可扩展性

可以灵活添加新字段而不破坏现有流程：

```json
{
  "existing_field": "...",
  "new_field": "..."  // 新增字段不影响现有处理
}
```

---

## 结构化约束的实施

### 1. 输入约束（Draft JSON）

由 `extract_papers.py` 生成，强制固定的字段结构：

```json
{
  "file": "string",              // PDF 文件名
  "title": "string",             // 来自 CSV
  "authors": "string",           // 来自 CSV
  "year": "integer",             // 来自 CSV
  "venue": "string",             // 来自 CSV
  "doi": "string",               // 来自 CSV
  "abstract": "string",          // 来自 CSV
  "body_text": "string",         // 来自 PDF 提取
  "citation_count": "string",    // 来自 CSV
  "relevance_score": "string",   // 来自 CSV
  "extraction_status": "string"  // 提取状态
}
```

**验证规则**：
- 必填字段：`title`, `body_text`
- 字段类型：`year` 必须是整数
- 状态枚举：`extraction_status` ∈ {"success", "failed"}

### 2. 输出约束（Analysis JSON）

由 Claude 生成，遵循 `skill/claude/analyze-paper-claude.md` 定义的格式：

```json
{
  "research_purpose": "string",           // 中文，1-3 句话
  "contributions": [                      // 数组，2-5 项
    {
      "point": "string",                  // 中文概括
      "evidence": "string"                // 英文原文
    }
  ],
  "theme_primary": "string",              // 枚举值，9 个主题簇之一
  "workstream_fit": "string",             // 枚举值，"1"/"2"/"3"
  "is_close_baseline_to_cute": "boolean"  // 布尔值
}
```

**枚举约束**：

#### Theme Clusters（主题簇）

1. CPU-side AI acceleration / in-core accelerator
2. Matrix extension / AMX / SME
3. Vector extension / RVV / vector AI enhancement
4. RISC-V custom ISA / open ISA AI extension
5. LLM / Transformer / inference acceleration
6. Quantization / mixed precision / FP8 / BF16 / block scale / mx
7. Compiler / tensor IR / operator generation
8. Memory hierarchy / scratchpad / dataflow / systolic
9. HBM / advanced packaging / multi-node system

#### Workstream Mapping（工作流映射）

- **"1"** — CPU 矩阵算力扩展 (CUTE)
- **"2"** — RVV AI 向量增强 + AI 辅助算子生成
- **"3"** — HBM + 高级封装 + 多节点 AI-CPU 系统架构

### 3. 审查约束（Review JSON）

由 GPT 生成，遵循 `skill/codex/paper-json-review/references/review-schema.md`：

```json
{
  "overall_verdict": "string",        // 枚举值
  "checks": {                         // 对象，键为检查项名
    "structure_compliant": "string",  // 枚举值
    "quotes_present": "string"
  },
  "field_reviews": [                  // 数组
    {
      "field": "string",              // 字段名
      "status": "string",             // 枚举值
      "severity": "string",           // 枚举值
      "reason": "string",
      "paper_evidence": "string",
      "suggested_fix": "string"
    }
  ],
  "issues": [                         // 数组
    {
      "field": "string",
      "severity": "string",
      "problem": "string",
      "paper_evidence": "string",
      "recommended_action": "string"
    }
  ]
}
```

**枚举值**：

- `overall_verdict`: "pass" | "minor_revision" | "major_revision" | "reject"
- `status`: "supported" | "partially_supported" | "incorrect" | "format_error"
- `severity`: "minor" | "major"

### 4. 预检脚本验证

`skill/codex/paper-json-review/scripts/preflight_review.py` 执行确定性检查：

```bash
python preflight_review.py \
    --analysis-json dossier.json \
    --paper-json paper.json \
    --pretty
```

**检查项**：
- 结构合规性：必需字段是否存在
- 元数据对齐：title/author/year 是否匹配
- 枚举值验证：theme/workstream 是否合法
- 引文存在性：evidence 字段是否为空
- 数值字符串：是否包含数字

**输出示例**：

```
✅ Structure compliant: All required fields present
✅ Metadata aligned: Title matches
✅ Allowed enums: theme_primary is valid
⚠️  Quotes present: Some evidence fields are empty
✅ Numeric strings: key_results contains numbers
```

---

## 关键节点的人工干预

### 节点 1：Web 审阅（Step 4）

**工具**：`review_server.py` + `review.html`

**时机**：在 LLM 处理之前，筛选高相关论文

**干预内容**：
- 标记论文为 keep/core/related/skip
- 添加个人笔记
- 根据摘要判断相关性

**价值**：
- 减少后续处理量（只处理 keep 论文）
- 避免低质量论文进入 LLM 流程
- 保留领域专家的判断

**数据流**：

```
scored.csv (14,600 篇)
    ↓
Web 审阅人工筛选
    ↓
keep 论文 (196 篇)
    ↓
extract_papers.py 处理
```

### 节点 2：Corpus 对照审阅（Step 8）

**工具**：`corpus_reviewer.py`

**时机**：在双模型生成之后

**干预内容**：
- 查看 LLM 分析与原文的对照
- 修正错误的提取
- 补充遗漏的要点
- 标记不确定的内容

**工作流**：

```
1. 查看 GPT Review (View 1)
   了解审查意见

   ↓

2. 参考 GLM Extraction (View 2)
   查看原始提取

   ↓

3. 查看 GPT Revised (View 3)
   查看修正版本

   ↓

4. 人工编辑 (View 4)
   最终修订并保存
```

**价值**：
- 捕捉 LLM 幻觉
- 补充领域知识
- 确保 proposal 论据准确
- 责任归属明确

### 节点 3：预检脚本（自动干预）

**工具**：`preflight_review.py`

**时机**：在 GPT 审查之前

**检查内容**：
- 结构合规性
- 元数据对齐
- 引文存在性
- 枚举值有效性

**价值**：
- 自动发现格式错误
- 减少人工审查负担
- 提供可追溯的检查报告

---

## 结构化与人工干预的协同

### 1. 结构化降低人工负担

**无结构化**：
```
人工阅读全文 → 手动提取信息 → 手动格式化 → 手动验证
```

**有结构化**：
```
LLM 提取 → 结构化输出 → 人工对照 → 快速修订
```

### 2. 人工干预确保质量

| 阶段 | 自动化 | 人工 | 理由 |
|------|--------|------|------|
| 论文筛选 | 关键词打分 | Web 审阅 | 领域判断 |
| 信息提取 | Claude 分析 | 预检脚本 | 格式验证 |
| 质量审查 | GPT 审查 | 人工审阅 | 准确性把关 |
| 最终修订 | - | 人工编辑 | 责任归属 |

### 3. 结构化便于审计

每个阶段都有结构化输出：

```
Draft JSON (extract_papers.py)
    ↓
Analysis JSON (Claude)
    ↓
Review JSON (GPT)
    ↓
Revised JSON (GPT)
    ↓
Human JSON (人工)
```

**审计能力**：
- 比较各版本差异
- 追溯错误来源
- 评估模型性能
- 改进提示词

### 4. 渐进式质量提升

```
第一轮：Claude 生成
    ↓ (结构化输出)
第二轮：GPT 审查
    ↓ (结构化审查)
第三轮：人工修订
    ↓ (最终版本)
```

每一步都基于前一步的结构化输出，逐步提升质量。

---

## 设计原则

### 1. 结构化优先

- 所有 LLM 输出必须是结构化 JSON
- 定义清晰的 Schema
- 使用枚举值限制自由度

### 2. 可验证性

- 自动验证格式正确性
- 预检脚本检查常见问题
- 审查报告标准化

### 3. 可追溯性

- 保留所有中间版本
- 记录来源和状态
- 支持版本比较

### 4. 人工最终把关

- 关键决策需要人工确认
- 领域判断无法自动化
- 责任需要明确归属

---

## 最佳实践

### 1. 从小规模开始

```
1. 处理 10 篇论文
2. 检查结构化输出质量
3. 调整提示词
4. 扩大到 50 篇
5. 继续迭代
```

### 2. 建立质量标准

- 定义"合格"的结构化输出
- 建立检查清单
- 定期审计

### 3. 利用结构化优势

- 编写脚本批量检查
- 可视化分析结果
- 自动化报告生成

### 4. 持续改进

- 收集错误案例
- 更新提示词
- 优化 Schema
- 改进预检规则
