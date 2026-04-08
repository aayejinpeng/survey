# Step 4: filter_papers.py

## 状态

计划中，当前仓库里还没有 `filter_papers.py`。

## 目标

从 `data/topics/{topic}/scored.csv` 中提取：

- `keep=yes`
- `keep=maybe`

或按 `--top N` / `--min-relevance` 生成 `filtered.csv`。

## 计划中的用法

```bash
python3 filter_papers.py \
    --input data/topics/cpu-ai/scored.csv \
    --output data/topics/cpu-ai/filtered.csv
```

## 预期行为

1. 读取 `scored.csv`
2. 按 `keep` 列或 `top N` 选出论文
3. 可叠加 `--min-relevance`
4. 输出 `filtered.csv`

## 当前替代方案

当前还没有脚本时，可以直接在 spreadsheet 中：

1. 打开 `scored.csv`
2. 填写 `keep`
3. 手工筛选出 `yes` / `maybe`
4. 导出成 `filtered.csv`
