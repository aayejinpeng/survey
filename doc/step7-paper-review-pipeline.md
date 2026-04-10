# Step 7: paper_review_pipeline.py — 双模型对抗生成 Pipeline

## 状态

✅ 已实现。

## 目标

自动化执行两阶段的 LLM 处理流程：
1. **Claude 分析**：读取 draft corpus JSON，生成结构化 dossier
2. **GPT 审查**：审查 Claude 生成的 dossier，输出审查意见和修正版本

通过异步生产者-消费者模式实现高效的批量处理。

## 常用命令

```bash
# 基本用法：处理整个 corpus
python3 paper_review_pipeline.py --topic cpu-ai

# 限制处理数量
python3 paper_review_pipeline.py --topic cpu-ai --limit 10

# 指定特定论文
python3 paper_review_pipeline.py --topic cpu-ai \
    --papers data/topics/cpu-ai/corpus/draft/paper1.json

# 重试失败的论文
python3 paper_review_pipeline.py --topic cpu-ai \
    --retry-failed-from runs/latest/summary.json

# 严格串行模式（无 pipeline 重叠）
python3 paper_review_pipeline.py --topic cpu-ai --strict-serial

# Dry run（仅打印命令，不执行）
python3 paper_review_pipeline.py --topic cpu-ai --dry-run
```

## 核心参数

| 参数 | 说明 | 默认值 |
|------|------|--------|
| `--topic` | 主题目录名（`data/topics/` 下） | `cpu-ai` |
| `--limit` | 处理论文数量限制 | `null` (全部) |
| `--papers` | 显式指定论文 JSON 路径 | - |
| `--corpus-dir` | 覆盖 corpus draft 目录 | 自动推导 |
| `--analysis-dir` | Claude 分析输出目录 | `corpus/llm/glm5.1/` |
| `--review-dir` | GPT 审查输出目录 | `corpus/llm/gpt5.4/` |
| `--log-dir` | 日志输出目录 | `corpus/paper_review_pipeline/` |
| `--queue-size` | Pipeline 队列大小 | 1 |
| `--strict-serial` | 禁用 pipeline 重叠 | `false` |
| `--skip-existing` | 跳过已存在的结果 | `false` |
| `--dry-run` | 仅打印命令不执行 | `false` |
| `--retry-failed-from` | 从之前的失败记录重试 | - |
| `--claude-timeout-sec` | Claude 超时时间（秒） | 1800 |
| `--codex-timeout-sec` | Codex 超时时间（秒） | 3600 |
| `--claude-max-retries` | Claude 最大重试次数 | 2 |
| `--codex-max-retries` | Codex 最大重试次数 | 3 |
| `--retry-backoff-sec` | 重试退避基数（秒） | 60 |

## 架构设计

### 生产者-消费者模式

```
┌─────────────────────────────────────────────────────────────┐
│                    paper_review_pipeline.py                   │
├─────────────────────────────────────────────────────────────┤
│                                                               │
│  ┌──────────────────┐         ┌──────────────────┐          │
│  │   Producer       │         │   Consumer       │          │
│  │   (Claude)       │   ──→   │   (Codex)        │          │
│  │                  │  Queue  │                  │          │
│  │  • 读取 draft    │         │  • 读取 analysis │          │
│  │  • 调用 Claude   │         │  • 调用 Codex    │          │
│  │  • 保存 GLM      │         │  • 保存 review   │          │
│  │    analysis.json │         │    + revised.json │          │
│  └──────────────────┘         └──────────────────┘          │
│         ↓                            ↓                       │
│  corpus/llm/glm5.1/           corpus/llm/gpt5.4/            │
└─────────────────────────────────────────────────────────────┘
```

### 并发控制

- **Pipelined 模式**（默认）：Claude 和 Codex 可以同时处理不同论文
- **Strict Serial 模式**：完全串行，一次只处理一篇论文
- **队列大小**：控制生产者领先消费者的任务数量

## 输出结构

```
corpus/
├── paper_review_pipeline/
│   ├── claude/
│   │   ├── {stem}.cmd.txt       # Claude 命令行
│   │   ├── {stem}.stdout.log    # Claude 标准输出
│   │   └── {stem}.stderr.log    # Claude 错误输出
│   ├── codex/
│   │   ├── {stem}.cmd.txt       # Codex 命令行
│   │   ├── {stem}.stdout.log    # Codex 标准输出
│   │   └── {stem}.stderr.log    # Codex 错误输出
│   ├── status/
│   │   ├── {stem}.claude.status.json  # Claude 实时状态
│   │   └── {stem}.codex.status.json   # Codex 实时状态
│   └── runs/
│       └── latest/
│           ├── summary.json           # 运行摘要
│           ├── failed_papers.json     # 失败论文列表
│           └── failed_papers.txt      # 失败论文列表（纯文本）
└── llm/
    ├── glm5.1/
    │   └── {stem}.json           # Claude 生成的 dossier
    └── gpt5.4/
        ├── {stem}.review.json     # Codex 审查报告
        └── {stem}.revised.json    # Codex 修正后的 dossier
```

## 运行摘要 (summary.json)

```json
{
  "generated_at_unix": 1712746800,
  "summary": [
    {
      "paper_json": "/path/to/draft/paper1.json",
      "analysis_json": "/path/to/llm/glm5.1/paper1.json",
      "review_json": "/path/to/llm/gpt5.4/paper1.review.json",
      "revised_json": "/path/to/llm/gpt5.4/paper1.revised.json",
      "claude_log_dir": "/path/to/paper_review_pipeline/claude",
      "codex_log_dir": "/path/to/paper_review_pipeline/codex",
      "analysis_status": "completed",
      "review_status": "completed",
      "analysis_duration_sec": 45.2,
      "review_duration_sec": 123.5
    }
  ],
  "failed_papers": [
    "/path/to/draft/failed_paper.json"
  ]
}
```

## 阶段状态文件

### 运行中状态

```json
{
  "stage": "claude",
  "job_name": "paper1.json",
  "state": "running",
  "pid": 12345,
  "started_at_unix": 1712746800,
  "elapsed_sec": 45.2,
  "timeout_sec": 1800,
  "cwd": "/root/opencute",
  "command": ["claude", "-p", "/analyze-paper-claude ..."]
}
```

### 完成状态

```json
{
  "stage": "claude",
  "job_name": "paper1.json",
  "state": "finished",
  "pid": 12345,
  "started_at_unix": 1712746800,
  "finished_at_unix": 1712746845,
  "elapsed_sec": 45.2,
  "timeout_sec": 1800,
  "returncode": 0,
  "stdout_tail": "...",
  "stderr_tail": "..."
}
```

## 容错与重试

### 失败分类

Pipeline 自动识别两类失败：

1. **可重试失败**：
   - HTTP 429 (Rate Limit)
   - 超时
   - 服务暂时不可用
   - 连接重置

2. **致命失败**：
   - API Key 无效
   - 权限不足
   - 文件不存在

### 重试策略

- **指数退避**：每次重试等待时间递增（`retry_backoff_sec * (attempt + 1)`）
- **最大重试次数**：Claude 2 次，Codex 3 次
- **连续失败保护**：Codex 连续 N 次失败后自动停止

### 重试失败论文

```bash
# 从 summary.json 重试
python3 paper_review_pipeline.py --topic cpu-ai \
    --retry-failed-from runs/latest/summary.json

# 从 failed_papers.json 重试
python3 paper_review_pipeline.py --topic cpu-ai \
    --retry-failed-from runs/latest/failed_papers.json
```

## 双模型对抗生成设计

### 为什么使用双模型？

1. **降低幻觉风险**
   - 第一个模型（Claude）负责生成
   - 第二个模型（GPT）负责审查
   - 交叉验证提高准确性

2. **专业性互补**
   - Claude：擅长长文本分析和结构化输出
   - GPT：擅长审查、验证和修正

3. **可追溯性**
   - 保留原始生成、审查意见和修正版本
   - 便于人工审核和质量评估

4. **质量保证**
   - 通过结构化的审查格式
   - 强制第二个模型检查特定维度

### 工作流程

```
Draft JSON (extract_papers.py 输出)
      ↓
┌─────────────────────────────────────┐
│  Stage 1: Claude 生成               │
│  • 读取 abstract + body_text        │
│  • 生成结构化 dossier               │
│  • 输出: glm5.1/{stem}.json         │
└─────────────────────────────────────┘
      ↓
┌─────────────────────────────────────┐
│  Stage 2: GPT 审查                  │
│  • 读取 glm5.1/{stem}.json          │
│  • 对照原文验证                     │
│  • 输出审查报告和修正版本           │
│  • 输出: gpt5.4/{stem}.review.json  │
│  • 输出: gpt5.4/{stem}.revised.json │
└─────────────────────────────────────┘
      ↓
人工审阅 (corpus_reviewer.py)
```

### Claude 生成内容

根据 `skill/claude/analyze-paper-claude.md`：

- 研究目的和意义
- 贡献点（带原文证据）
- 主题分类
- 关键技术和结果
- 研究空白（带原文证据）
- Proposal 论据

### GPT 审查维度

根据 `skill/codex/paper-json-review/SKILL.md`：

1. **结构合规性**：字段完整、类型正确
2. **引文准确性**：英文证据是否存在于原文
3. **语义可信度**：中文总结是否准确
4. **数值准确性**：性能数据、实验结果
5. **分类正确性**：主题、工作流、基线判断

## 用户工作流

```
extract_papers.py → corpus/draft/*.json
      ↓
paper_review_pipeline.py → corpus/llm/{glm5.1,gpt5.4}/*.json
      ↓
corpus_reviewer.py → 人工对照审阅
      ↓
human_review/ → 最终修订版本
```

## 注意事项

1. **API 费用**：双模型处理会产生 API 费用，建议先用 `--limit` 测试
2. **处理时间**：每篇论文约需 3-5 分钟（Claude ~1min，GPT ~2-4min）
3. **并发控制**：queue_size 不宜过大，避免速率限制
4. **日志监控**：实时查看 status/ 目录了解处理进度
5. **失败重试**：优先使用 `--retry-failed-from` 而非重新运行

## 最佳实践

### 1. 分批处理

```bash
# 先处理 10 篇测试
python3 paper_review_pipeline.py --topic cpu-ai --limit 10

# 检查结果质量后再继续
python3 paper_review_pipeline.py --topic cpu-ai --limit 50
```

### 2. 监控进度

```bash
# 实时查看状态
watch -n 5 'ls -la corpus/paper_review_pipeline/status/*.claude.status.json | tail -5'
```

### 3. 处理失败

```bash
# 查看失败论文
cat runs/latest/failed_papers.txt

# 重试失败论文
python3 paper_review_pipeline.py --topic cpu-ai \
    --retry-failed-from runs/latest/summary.json
```

### 4. 质量检查

```bash
# 启动审阅工具
python3 corpus_reviewer.py --topic cpu-ai

# 检查几篇论文的质量
# 如果质量不理想，调整 skill 提示词后重试
```

## 扩展性

### 添加新的分析模型

修改 `claude_command()` 函数：

```python
def claude_command(job: PaperJob, args: argparse.Namespace) -> list[str]:
    command = [
        "other-llm-cli",  # 替换为其他 CLI
        "-p", f"/custom-skill {job.paper_json}",
        ...
    ]
    return command
```

### 添加新的审查模型

修改 `codex_command()` 函数：

```python
def codex_command(job: PaperJob, args: argparse.Namespace) -> list[str]:
    return [
        "bash",
        str(args.custom_review_script),  # 自定义审查脚本
        str(job.analysis_json),
        ...
    ]
```

## 与上游下游集成

- **上游**：读取 `extract_papers.py` 生成的 draft JSON
- **下游**：输出供 `corpus_reviewer.py` 使用的结构化分析

## 故障排除

### Claude 超时

- 增加超时时间：`--claude-timeout-sec 3600`
- 检查论文长度，可能需要截断
- 查看 stderr 日志了解卡在哪个阶段

### Codex 失败

- 检查 Codex skill 是否正确安装
- 验证 Claude 输出格式是否正确
- 查看 `preflight_review.py` 输出

### 队列阻塞

- 降低 `--queue-size`
- 使用 `--strict-serial` 模式
- 检查 Codex 处理速度
