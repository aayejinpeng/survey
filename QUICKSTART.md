# Survey Pipeline - 5分钟上手指南

## 一句话说清楚

> **一个自动化工具，帮你从海量论文中筛选出真正有价值的，并用 AI 提取精华内容，直接用于开题报告写作。**

---

## 能帮你解决什么问题？

写开题报告时最烦的几件事：
- ❌ 不知道去哪找相关论文
- ❌ 找到一堆论文，没时间一篇篇看
- ❌ 看完了，整理不出能直接用的素材
- ❌ 引文、数据、贡献点...全要手动抄

**Survey Pipeline 全帮你搞定**：
1. 自动从 DBLP 抓取论文（27个顶级会议+7个期刊）
2. 用关键词自动打分排序
3. Web 界面快速浏览筛选
4. AI 自动提取：研究目的、贡献点、实验数据、研究空白
5. AI 双重验证（一个生成，一个审查），保证准确性
6. 对照 PDF 人工审核，一键导出

---

## 新手练手指南（3步走）

### 第1步：配置你要抓的会议/期刊

编辑 `configs/venues.yaml`：

```yaml
venues:
  # 计算机体系结构顶会
  - id: ISCA
    dblp_key: conf/isca

  - id: MICRO
    dblp_key: conf/micro

  - id: ASPLOS
    dblp_key: conf/asplos

  - id: HPCA
    dblp_key: conf/hpca

  # 处理器会议
  - id: DAC
    dblp_key: conf/dac

  - id: ISSCC
    dblp_key: conf/isscc

  # 期刊
  - id: IEEE-TC
    dblp_key: journals/tc

  - id: IEEE-TCA
    dblp_key: journals/tc

date_range:
  start: 2022    # 从哪年开始
  end: 2026      # 到哪年结束
```

**怎么找你想要的会议？**
1. 访问 [DBLP](https://dblp.org/)
2. 搜索会议名称（比如 "CVF"）
3. 看URL里的路径，比如 `dblp.org/db/conf/cvf/`
4. 填入 `dblp_key: conf/cvf`

---

### 第2步：配置你的研究主题

编辑 `configs/topic-cpu-ai.yaml`：

```yaml
topic: "CPU AI 加速研究"

keywords:
  # 核心关键词（权重10）：出现就给高分
  - term: "AMX"
    weight: 10

  - term: "matrix extension"
    weight: 10

  - term: "NPU"
    weight: 10

  - term: "in-core accelerator"
    weight: 10

  # 重要关键词（权重5）
  - term: "RISC-V"
    weight: 5

  - term: "vector extension"
    weight: 5

  - term: "RVV"
    weight: 5

  - term: "tensor"
    weight: 5

  # 相关关键词（权重3）
  - term: "neural network"
    weight: 3

  - term: "deep learning"
    weight: 3

  - term: "inference"
    weight: 3

  # 扩展关键词（权重1）：扩大召回范围
  - term: "AI"
    weight: 1

  - term: "acceleration"
    weight: 1

  - term: "performance"
    weight: 1
```

**权重怎么设置？**
| 权重 | 含义 | 使用场景 |
|------|------|----------|
| 10 | 核心词 | 出现这篇论文肯定相关 |
| 5 | 重要词 | 很可能相关 |
| 3 | 相关词 | 可能相关 |
| 1 | 扩展词 | 扩大搜索范围，避免漏掉 |

**打分规则**：所有匹配关键词的权重相加
- score >= 10：高度相关
- score >= 5：中度相关
- score >= 1：可能相关

---

### 第3步：一键运行

```bash
# 1. 抓取论文
python3 fetch_dblp.py --config configs/venues.yaml --output-dir data/db/

# 2. 补充摘要和引用数（这步要几分钟）
python3 enrich_papers.py --input-dir data/db/ --output-dir data/enriched/

# 3. 按关键词打分
python3 score_papers.py \
    --input-dir data/enriched/ \
    --topic-config configs/topic-cpu-ai.yaml \
    --output-dir data/topics/cpu-ai/

# 4. 查看高分论文
head -20 data/topics/cpu-ai/scored.csv
```

---

## 创建你自己的主题配置

### 示例1：大模型优化方向

```yaml
topic: "大模型推理优化"

keywords:
  - term: "LLaMA"
    weight: 10
  - term: "LLM inference"
    weight: 10
  - term: "KV cache"
    weight: 8
  - term: "quantization"
    weight: 5
  - term: "transformer"
    weight: 3
```

### 示例2：RISC-V 方向

```yaml
topic: "RISC-V 处理器设计"

keywords:
  - term: "RISC-V"
    weight: 10
  - term: "RVV"
    weight: 8
  - term: "RISC-V core"
    weight: 8
  - term: "open source"
    weight: 3
```

### 示例3：存算一体方向

```yaml
topic: "存算一体架构"

keywords:
  - term: "processing-in-memory"
    weight: 10
  - term: "PIM"
    weight: 10
  - term: "compute-in-memory"
    weight: 10
  - term: "memristor"
    weight: 5
  - term: "ReRAM"
    weight: 5
```

---

## 进阶玩法：AI 自动提取论文精华

```bash
# 5. Web 界面快速筛选（浏览器打开 http://localhost:8088）
python3 review_server.py \
    --csv data/topics/cpu-ai/scored.csv \
    --topic configs/topic-cpu-ai.yaml

# 6. 下载你标记的论文 PDF（需要 Zotero）
python3 sync_zotero.py \
    --input data/topics/cpu-ai/scored.csv \
    --output-dir pdfs/cpu-ai/

# 7. AI 自动提取精华（Claude 生成 + GPT 审查）
python3 paper_review_pipeline.py --topic cpu-ai --limit 10

# 8. 对照 PDF 人工审核
python3 corpus_reviewer.py --topic cpu-ai
```

---

## 文件位置速查

| 文件 | 位置 | 说明 |
|------|------|------|
| 会议配置 | `configs/venues.yaml` | 要抓哪些会议/期刊 |
| 主题配置 | `configs/topic-cpu-ai.yaml` | 研究主题关键词 |
| 原始数据 | `data/db/` | DBLP 抓取的原始数据 |
| 富化数据 | `data/enriched/` | 带摘要和引用数的数据 |
| 打分结果 | `data/topics/{topic}/scored.csv` | 按相关性排序的论文列表 |
| PDF | `pdfs/{topic}/` | 下载的论文 PDF |
| AI 提取结果 | `data/topics/{topic}/corpus/` | AI 提取的精华内容 |

---

## 常见问题

**Q: 能抓中文论文吗？**
A: 当前主要抓 DBLP 的英文论文，中文期刊需要手动添加。

**Q: 抓取要多久？**
A: 14,600篇论文约5-10分钟，主要是网络请求时间。

**Q: AI 分析要花钱吗？**
A: 是的，调用 Claude 和 GPT API 需要付费。建议先小批量测试（--limit 10）。

**Q: 可以只免费部分吗？**
A: 可以！前3步（抓取、富化、打分）完全免费，只是少了 AI 自动提取功能。

---

## 项目特色

| 特性 | 说明 |
|------|------|
| 📊 **数据全面** | 27个顶会 + 7个期刊，覆盖计算机体系结构全领域 |
| 🤖 **AI 加持** | Claude 生成 + GPT 审查，双重验证保证质量 |
| 👀 **人工把关** | Web 界面对照 PDF 审核，绝不盲信 AI |
| 📦 **即开即用** | 结构化输出，直接用于开题报告写作 |
| 🔄 **可扩展** | 轻松添加新的会议、期刊、研究主题 |

---

## 适用场景

- ✅ 写开题报告，需要调研大量论文
- ✅ 找研究方向，想了解某个领域的研究现状
- ✅ 写文献综述，需要系统梳理前人工作
- ✅ 找研究空白，需要识别未解决的问题
- ✅ 准备基金申请，需要充分的调研材料

---

**开始你的第一次论文调研吧！** 🚀

有问题？看完整文档：[README.md](README.md)
