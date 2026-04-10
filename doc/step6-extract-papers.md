# Step 6: extract_papers.py — PDF 解析与 Draft Corpus 生成

## 状态

✅ 已实现。

## 目标

从下载的 PDF 文件中提取正文文本，结合 CSV 中的元数据，生成结构化的 draft corpus JSON 文件，为后续的 LLM 分析提供标准化输入。

## 常用命令

```bash
python3 extract_papers.py \
    pdfs/cpu-ai/ \
    data/topics/cpu-ai/scored-score-gte11.csv \
    -o data/topics/cpu-ai/corpus/draft/
```

## 当前支持参数

| 参数 | 说明 | 必需 |
|------|------|------|
| `pdf_dir` | PDF 文件所在目录 | ✅ |
| `csv` | 评分后的 CSV 文件 | ✅ |
| `-o, --output` | 输出目录（将创建 corpus JSON） | ✅ |
| `-n, --limit` | 仅处理前 N 个 PDF（0=全部） | ❌ |

## 功能特性

### 1. PDF 文本提取

- **双引擎支持**：优先使用 PyMuPDF (fitz)，失败时回退到 pdfplumber
- **智能截断**：在 References 章节自动停止，避免提取参考文献列表
- **噪声清理**：自动移除页眉、页脚、版权声明、DOI 行等

### 2. 元数据合并

从 CSV 中读取以下元数据：

| 字段 | 来源 | 说明 |
|------|------|------|
| `title` | CSV | 论文标题 |
| `authors` | CSV | 作者列表 |
| `year` | CSV | 发表年份 |
| `venue` | CSV | 会议/期刊名称 |
| `doi` | CSV | DOI 标识符 |
| `url` | CSV | 论文链接 |
| `abstract` | CSV | 摘要 |
| `citation_count` | CSV | 引用数 |
| `relevance_score` | CSV | 相关性评分 |
| `relevance` | CSV | 相关性等级 |
| `matched_keywords` | CSV | 匹配的关键词 |

### 3. 文件名匹配

使用模糊匹配将 PDF 文件名与 CSV 记录关联：

- 标准化文件名（移除特殊字符、转小写）
- 子串匹配（PDF 文件名可以是标题的一部分或反之）
- 支持各种 PDF 文件名格式

### 4. 质量控制

- **最小长度检查**：提取文本少于 200 字符标记为失败
- **匹配状态跟踪**：记录是否成功匹配 CSV 记录
- **详细日志**：每个文件的处理状态、文本长度

## 输出格式

### 单个论文 JSON

```json
{
  "file": "A-Heterogeneous-CNN-Compilation-Framework-for-RISC-V-CPU-and-NPU-Integration-Bas.pdf",
  "title": "A Heterogeneous CNN Compilation Framework for RISC-V CPU and NPU Integration",
  "authors": "Author1, Author2",
  "year": 2024,
  "venue": "Conference Name",
  "doi": "10.xxx/xxxx",
  "url": "https://...",
  "abstract": "摘要内容...",
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

### 索引文件 (index.json)

```json
{
  "total": 196,
  "success": 180,
  "failed": 10,
  "no_csv_match": 6,
  "papers": [
    {
      "file": "paper1.pdf",
      "json": "paper1.json",
      "title": "Paper Title",
      "venue": "Conference",
      "year": 2024,
      "doi": "10.xxx/xxxx",
      "citation_count": "10",
      "relevance_score": "15",
      "relevance": "High",
      "text_length": 15000,
      "csv_matched": true,
      "status": "success"
    }
  ]
}
```

## 用户工作流

```
sync_zotero.py → pdfs/cpu-ai/*.pdf
      ↓
extract_papers.py → corpus/draft/*.json
      ↓
paper_review_pipeline.py → corpus/llm/{glm5.1,gpt5.4}/*.json
```

## 噪声清理规则

自动移除以下噪声：

- 版权声明
- 下载信息
- 会议信息页眉
- ISBN/DOI 行
- 孤立页码
- "Keywords" 标题
- 许可证声明
- ACM 参考格式行
- 孤立的点号行

## References 检测

支持多种 References 章节标题格式：

- `References`
- `Bibliography`
- `References` (带编号前缀)
- 大小写不敏感匹配

## 故障排除

### PDF 提取失败

1. 检查 PDF 是否损坏
2. 尝试手动打开 PDF 确认可读性
3. 查看日志了解具体错误

### CSV 匹配失败

1. 检查 PDF 文件名是否与标题相关
2. 查看 `no_csv_match` 统计
3. 可能需要手动重命名 PDF 文件

### 文本长度不足

1. PDF 可能是扫描版（图像而非文本）
2. 可能使用了非标准字体编码
3. 尝试用其他 PDF 阅读器打开验证

## 注意事项

- 处理时间取决于 PDF 数量和大小
- 大型 corpus 建议分批处理（使用 `--limit`）
- 输出目录会自动创建，无需手动准备
- CSV 中的元数据优先级高于 PDF 中的元数据

## 与下游步骤的集成

draft corpus JSON 是以下步骤的输入：

1. **paper_review_pipeline.py**：读取 draft JSON 进行 Claude 分析
2. **corpus_reviewer.py**：提供原始论文数据用于对照
3. **后续分析**：作为论文语料库的基础数据

## 设计理念

### 为什么需要结构化 Draft？

1. **标准化输入**：为 LLM 提供统一、可预测的输入格式
2. **元数据丰富**：CSV 中的结构化元数据（引用数、相关性评分）帮助 LLM 理解论文重要性
3. **正文干净**：经过噪声清理的正文文本，减少 LLM 处理的干扰
4. **可追溯**：保留提取状态（success/failed），便于问题排查
5. **可扩展**：结构化格式便于添加新的元数据字段
