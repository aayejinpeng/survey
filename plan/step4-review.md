# Step 4: review_server.py + review.html — Web 审阅工具

## 状态

✅ 已实现。

> **设计变更**：原计划为 `filter_papers.py`（在 spreadsheet 中标记），实际改为 Web 审阅方案，体验更好。

## 目标

提供本地 Web 审阅界面，对 `scored.csv` 或截取后的子集进行人工审阅和标记，标记结果写回 CSV。

## CLI

```bash
python3 review_server.py \
    --csv data/topics/cpu-ai/scored-score-gte11.csv \
    --topic configs/topic-cpu-ai.yaml
```

| 参数 | 说明 |
|------|------|
| `--csv` | 要审阅的 CSV 文件 |
| `--topic` | topic 配置 YAML（用于关键词高亮） |
| `--port` | 服务端口（默认 8088） |

## 功能设计

- **2x2 网格布局**：同时展示 4 篇论文摘要
- **关键词金色高亮**：按权重从暗到亮渐变，一眼看出匹配度
- **自定义标签**：keep / core / related / skip + 自由输入
- **键盘快捷键**：`1234`=keep, `qwer`=skip, `←→`=翻页, `Ctrl+S`=保存
- **持久化**：标记写回 CSV 的 `keep` 和 `notes` 列
- **跳过已标记**：已标记的论文自动跳过

## 数据流

```
slice_csv.py → scored-score-gte11.csv
       ↓
review_server.py → 浏览器审阅 → 标记 keep/skip
       ↓
CSV 原地更新 keep/notes 列
       ↓
sync_zotero.py 读取 keep 列下载 PDF
```
