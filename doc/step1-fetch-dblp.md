# Step 1: fetch_dblp.py

## 状态

已实现。

## 目标

从 `configs/venues.yaml` 读取 venue 和年份范围，抓取 DBLP proceedings 或 journal 页面，输出到 `data/db/`。

## 常用命令

```bash
python3 fetch_dblp.py --config configs/venues.yaml --output-dir data/db/
python3 fetch_dblp.py --config configs/venues.yaml --output-dir data/db/ --venues ISCA,MICRO
python3 fetch_dblp.py --config configs/venues.yaml --output-dir data/db/ --years 2024
python3 fetch_dblp.py --config configs/venues.yaml --output-dir data/db/ --force
```

## 输入

- `configs/venues.yaml`

关键字段：

```yaml
venues:
  - id: ISCA
    dblp_key: conf/isca
  - id: MICRO
    dblp_key: conf/micro

date_range:
  start: 2023
  end: 2026
```

## 输出

- `data/db/{venue}-{year}.csv`

输出列：

- `paper_id`
- `title`
- `authors`
- `year`
- `venue`
- `doi`
- `url`
- `dblp_id`

## 实际行为

1. 读取 venue 列表和年份范围
2. 逐个抓取 proceedings 或 journal volume 页面
3. 从 DBLP HTML 中抽取标题、作者、DOI、记录 ID
4. 同一文件内按 DOI 去重
5. 写入 `data/db/`

## 已知特性

- conference 和 journal 都支持
- 429 / 5xx / `IncompleteRead` 会自动重试
- proceedings 缺失时不会中断整批任务
- 默认跳过已有文件；只有 `--force` 才覆盖

## 注意

- `--venues` 和 `--years` 当前使用逗号分隔字符串，不是重复多次传参
- DBLP HTML 结构如果变化，解析逻辑可能需要调整
