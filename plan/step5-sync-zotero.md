# Step 5: sync_zotero.py — Zotero PDF 同步

## 状态

✅ 已实现。

> **设计变更**：原计划 Step 5 为 `build_graph.py`（引用图），实际先实现了 PDF 同步（更优先的需求）。引用图构建推迟到 Step 6。

## 目标

从 Zotero 本地 API 按 DOI 下载 keep 论文的 PDF 到本地目录。

## 前置条件

- Zotero 桌面版运行中，本地 API 已启用（默认 `localhost:23119`）
- 论文已通过 DOI 或 RIS 导入 Zotero
- Zotero 已同步/挂载 PDF 附件

## CLI

```bash
python3 sync_zotero.py \
    --input data/topics/cpu-ai/scored-score-gte11.csv \
    --output-dir pdfs/cpu-ai/

python3 sync_zotero.py \
    --input data/topics/cpu-ai/scored-score-gte11.csv \
    --output-dir pdfs/cpu-ai/ \
    --dry-run

python3 sync_zotero.py \
    --input data/topics/cpu-ai/scored-score-gte11.csv \
    --output-dir pdfs/cpu-ai/ \
    --port 23119
```

| 参数 | 说明 |
|------|------|
| `--input` | 输入 CSV（含 DOI 和 keep 列） |
| `--output-dir` | PDF 下载目录 |
| `--dry-run` | 只检查不下载 |
| `--port` | Zotero 本地 API 端口（默认 23119） |

## 行为

1. 读取 CSV 中 `keep=yes` 的论文
2. 逐个用 DOI 在 Zotero 本地 API 中查找
3. 找到后下载关联的 PDF 附件
4. PDF 以 `{first_author}-{year}-{short_title}.pdf` 格式保存
5. 输出 `doi-list.txt`

## 输出

- `pdfs/{topic}/*.pdf` — PDF 文件
- `pdfs/{topic}/doi-list.txt` — 已下载论文的 DOI 列表

## 替代方案 A：手动下载（export_dois.py）

Zotero 不可用时，用 `export_dois.py` 生成可点击 DOI 链接，逐个手动下载：

```bash
python3 export_dois.py --input data/topics/cpu-ai/scored-score-gte11.csv
python3 export_dois.py --input data/topics/cpu-ai/scored-score-gte11.csv --tag core
```

输出 `doi-list.txt`，每行一条 `https://doi.org/...` 链接，带论文标题注释，浏览器直接打开即可下载。

## 替代方案 B：远程 Zotero（NFS 挂载）

Zotero 在远程机器时：

1. 远程导出 NFS share：`~/Zotero *(ro,sync,no_subtree_check)`
2. 本机挂载：`sudo mount -t nfs remote-host:/home/user/Zotero /mnt/zotero`
3. 从 `storage/` 目录复制 PDF
4. 或用 `sync_zotero.py --host remote-host` 直接访问远程 API
