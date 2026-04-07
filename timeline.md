# Survey Pipeline — Timeline（v2: Venue-Based）

## 基线

- 项目启动：2026-04-07
- v1→v2 重构：按 venue+year 从 DBLP 获取论文（方案 3: HTML Proceedings）
- 当前目标：先打通 `DBLP fetch → S2 enrich → abstract fallback → CSV` 主链路
- 关键路径：Phase 0 → Phase 1 → Phase 2 → Phase 3 → Phase 4 → Review

## 建议排期

| Phase | 内容 | 依赖 | 状态 | 负责人 | 目标开始 | 目标完成 | Gate |
|-------|------|------|------|--------|----------|----------|------|
| Phase 0 | contract + DBLP 连通性验证 | - | 🔄 In Progress | Claude | 2026-04-07 | 2026-04-07 | DBLP HTML 解析通 |
| Phase 1 | `survey_crawler.py` 重构（DBLP + enrichment） | Phase 0 | ⬜ Pending | Claude | 2026-04-08 | 2026-04-09 | venue×year 获取 + enrichment + CSV |
| Phase 2 | `survey-crawl.md` + `survey-filter.md` | Phase 1 | ⬜ Pending | Claude | 2026-04-09 | 2026-04-09 | 同 topic 重跑不丢 `keep/notes` |
| Phase 3 | `citation_graph.py` + `survey-graph.md` | Phase 1-2 | ⬜ Pending | Claude | 2026-04-10 | 2026-04-10 | mixed-ID filtered CSV 可正常出图 |
| Phase 4 | `survey-update.md` + update mode | Phase 1-3 | ⬜ Pending | Claude | 2026-04-11 | 2026-04-11 | 增量 update 通过 |
| Review | 全流程 demo 测试 + GPT review | Phase 1-4 | ⬜ Pending | User + GPT | 2026-04-11 | 2026-04-11 | 端到端 smoke 通过 |

## Phase 0 细节

| Step | 任务 | 状态 |
|------|------|------|
| 0.1 | 验证 DBLP proceedings HTML 结构（ISCA 2024 为例） | 🔄 |
| 0.2 | 锁定 HTML 解析策略（CSS selectors） | ⬜ |
| 0.3 | 验证 S2 DOI lookup、Crossref DOI lookup、arXiv ID lookup | ⬜ |
| 0.T | Gate 0：DBLP fetch + 三个 enrichment API 都连通 | ⬜ |

## Phase 1 细节（v2 重构）

| Step | 任务 | 状态 |
|------|------|------|
| 1.1 | 配置加载 + 状态管理（新 config.yaml 格式） | ⬜ |
| 1.2 | DBLP HTML proceedings 解析（fetch + parse） | ⬜ |
| 1.3 | S2 enrichment（via DOI → citation_count, abstract, s2_paper_id） | ⬜ |
| 1.4 | Abstract fallback chain（Crossref → arXiv → 标记不可用） | ⬜ |
| 1.5 | 关键词排序 | ⬜ |
| 1.6 | Merge-safe CSV 写入（full / update） | ⬜ |
| 1.7 | 状态更新（crawled_venues + seen_paper_ids） | ⬜ |
| 1.T | Gate 1：ISCA 2024 全流程验证 | ⬜ |

## Phase 2 细节

| Step | 任务 | 状态 |
|------|------|------|
| 2.1 | `survey-crawl.md`：生成/复用配置，触发 full crawl | ⬜ |
| 2.2 | `survey-filter.md`：抽取 `keep=yes/maybe` | ⬜ |
| 2.T | Gate 2：同 topic 端到端重跑不丢人工列 | ⬜ |

## Phase 3 细节

| Step | 任务 | 状态 |
|------|------|------|
| 3.1 | 读取 filtered CSV（含 `arxiv_id` / `s2_paper_id`） | ⬜ |
| 3.2 | S2 ID resolve + 引用关系获取 + 缓存 | ⬜ |
| 3.3 | `networkx` 有向图构建 | ⬜ |
| 3.4 | `matplotlib` 渲染 | ⬜ |
| 3.5 | DOT 文件输出 | ⬜ |
| 3.6 | 统计摘要 `stats.md` | ⬜ |
| 3.7 | `survey-graph.md` skill | ⬜ |
| 3.T | Gate 3：mixed-ID 样本出图验证 | ⬜ |

## Phase 4 细节

| Step | 任务 | 状态 |
|------|------|------|
| 4.1 | `survey_crawler.py` update 模式 | ⬜ |
| 4.2 | `survey-update.md` skill | ⬜ |
| 4.3 | 同一窗口重复 update 的幂等验证 | ⬜ |
| 4.T | Gate 4：增量更新验证通过 | ⬜ |

## 变更记录

| 日期 | 变更 |
|------|------|
| 2026-04-07 | 项目启动，方案拆分为 4 个 Phase |
| 2026-04-07 | timeline 修订为带 Gate 的建议排期，新增 Phase 0 |
| 2026-04-07 | v2 重构：改为 DBLP venue-based 获取（方案 3: HTML Proceedings）+ S2/Crossref/arXiv enrichment |
