# Step 5: sync_zotero.py — Zotero PDF 同步

## 状态

✅ 已实现。

## 目标

从 Zotero 本地 API 按 DOI 下载 keep 论文的 PDF 到本地目录。

## 前置条件

- Zotero 桌面版运行中，且本地 API 已启用（默认 `localhost:23119`）
- 论文已通过 DOI 或 RIS 导入 Zotero
- Zotero 已同步/挂载 PDF 附件

## 常用命令

```bash
# 下载所有 keep 论文的 PDF
python3 sync_zotero.py \
    --input data/topics/cpu-ai/scored-score-gte11.csv \
    --output-dir pdfs/cpu-ai/

# 预演（只检查 Zotero 中有哪些，不实际下载）
python3 sync_zotero.py \
    --input data/topics/cpu-ai/scored-score-gte11.csv \
    --output-dir pdfs/cpu-ai/ \
    --dry-run

# 自定义 Zotero 端口
python3 sync_zotero.py \
    --input data/topics/cpu-ai/scored-score-gte11.csv \
    --output-dir pdfs/cpu-ai/ \
    --port 23119
```

## 当前支持参数

| 参数 | 说明 |
|------|------|
| `--input` | 输入 CSV 文件（含 DOI 和 keep 列） |
| `--output-dir` | PDF 下载目录 |
| `--dry-run` | 只检查不下载 |
| `--port` | Zotero 本地 API 端口（默认 23119） |

## 行为

1. 读取 CSV 中 `keep=yes` 的论文
2. 逐个用 DOI 在 Zotero 本地 API 中查找
3. 找到后下载关联的 PDF 附件
4. PDF 以 `{first_author}-{year}-{short_title}.pdf` 格式保存
5. 输出 `doi-list.txt`（已成功下载的 DOI 列表）

## 输出

- `pdfs/{topic}/` — PDF 文件
- `pdfs/{topic}/doi-list.txt` — 已下载论文的 DOI 列表

## 替代方案 A：手动下载（export_dois.py）

如果 Zotero 不可用，可以用 `export_dois.py` 生成可点击的 DOI 链接列表，逐个手动下载 PDF。

```bash
# 导出 keep 论文的 DOI 链接
python3 export_dois.py \
    --input data/topics/cpu-ai/scored-score-gte11.csv

# 指定输出路径
python3 export_dois.py \
    --input data/topics/cpu-ai/scored-score-gte11.csv \
    --output pdfs/cpu-ai/doi-list.txt

# 只导出 core 标签的论文
python3 export_dois.py \
    --input data/topics/cpu-ai/scored-score-gte11.csv \
    --tag core
```

| 参数 | 说明 |
|------|------|
| `--input` | 输入 CSV（含 DOI 和 keep 列） |
| `--output` | 输出文件路径（默认 `<input_dir>/doi-list.txt`） |
| `--tag` | 按标签过滤（默认 `keep`） |

输出文件格式（可直接在浏览器中点击每个链接）：

```
# 1. 论文标题
#    会议 年份
https://doi.org/10.1109/ICCD65941.2025.00092
```

## 替代方案 B：远程 Zotero（NFS 挂载）

如果 Zotero 运行在远程机器上，本机无法直接访问其 local API，可以通过 NFS 挂载 Zotero 的存储目录来获取 PDF。

**步骤：**

1. 在 Zotero 所在机器上，导出 Zotero data 目录（通常 `~/Zotero/`）为 NFS share：

```bash
# /etc/exports
/home/user/Zotero  *(ro,sync,no_subtree_check)
```

2. 在本机挂载：

```bash
sudo mount -t nfs remote-host:/home/user/Zotero /mnt/zotero
```

3. 直接从挂载目录复制 PDF：

```bash
# Zotero PDF 存储在 storage/ 下，按 item key 分目录
# 可结合 doi-list.txt 中的 DOI 手动查找对应 PDF
cp /mnt/zotero/storage/*/fulltext.pdf pdfs/cpu-ai/
```

4. 也可以用 `sync_zotero.py` 的 `--host` 参数指向远程 Zotero（如果网络可达）：

```bash
python3 sync_zotero.py \
    --input data/topics/cpu-ai/scored-score-gte11.csv \
    --output-dir pdfs/cpu-ai/ \
    --host remote-host
```

## 注意

- 本地方式需要先启动 Zotero 桌面版
- 如果 Zotero 中没有对应论文或没有 PDF 附件，该论文会被跳过
- 已存在的 PDF 不会重复下载
- 远程 NFS 挂载需要适当权限配置，建议只读挂载
