# Step 4: review_server.py + review.html — Web 审阅工具

## 状态

✅ 已实现。

## 目标

提供本地 Web 审阅界面，对 `scored.csv` 或截取后的子集进行人工审阅和标记，标记结果写回 CSV。

## 常用命令

```bash
python3 review_server.py \
    --csv data/topics/cpu-ai/scored-score-gte11.csv \
    --topic configs/topic-cpu-ai.yaml
```

服务启动后浏览器打开 `http://localhost:8088`。

## 当前支持参数

| 参数 | 说明 |
|------|------|
| `--csv` | 要审阅的 CSV 文件 |
| `--topic` | topic 配置 YAML（用于关键词高亮） |
| `--port` | 服务端口（默认 8088） |

## 功能

- **2x2 网格布局**：同时展示 4 篇论文摘要
- **关键词金色高亮**：按权重从暗到亮渐变，一眼看出匹配度
- **自定义标签**：keep / core / related / skip + 自由输入
- **键盘快捷键**：
  - `1234` = 对应位置的论文标记 keep
  - `qwer` = 对应位置的论文标记 skip
  - `←→` = 翻页
  - `Ctrl+S` = 保存
- **持久化**：标记写回 CSV 的 `keep` 和 `notes` 列
- **跳过已标记**：已标记的论文自动跳过，专注于未审阅的

## 用户工作流

```
slice_csv.py → scored-score-gte11.csv
      ↓
review_server.py → 浏览器审阅 → 标记 keep/skip
      ↓
sync_zotero.py → 下载 keep 论文的 PDF
```

## 注意

- 服务在本地运行，不需要外部部署
- CSV 在每次保存时原地更新，建议提前备份
- `--topic` 参数决定高亮的关键词和权重
