# Survey Pipeline — Timeline

## 基线

- 项目启动：2026-04-07
- 当前目标：先打通 `full crawl -> filter -> graph` 主链路，再交付 `update`
- 关键路径：Phase 0 → Phase 1 → Phase 2 → Phase 3 → Phase 4 → Review

## 建议排期

| Phase | 内容 | 依赖 | 状态 | 负责人 | 目标开始 | 目标完成 | Gate |
|-------|------|------|------|--------|----------|----------|------|
| Phase 0 | contract + fixture + acceptance baseline | - | ⬜ Pending | User + Claude | 2026-04-07 | 2026-04-07 | `paper_id/arxiv_id/s2_paper_id` 定稿 |
| Phase 1 | `survey_crawler.py` 爬取编排器 | Phase 0 | ⬜ Pending | Claude | 2026-04-08 | 2026-04-09 | full crawl 可正确 dedupe 并保留人工列 |
| Phase 2 | `survey-crawl.md` + `survey-filter.md` | Phase 1 | ⬜ Pending | Claude | 2026-04-09 | 2026-04-09 | 同 topic 重跑不丢 `keep/notes` |
| Phase 3 | `citation_graph.py` + `survey-graph.md` | Phase 1-2 | ⬜ Pending | Claude | 2026-04-10 | 2026-04-10 | mixed-ID filtered CSV 可正常出图 |
| Phase 4 | `survey-update.md` + update mode | Phase 1-3 | ⬜ Pending | Claude | 2026-04-11 | 2026-04-11 | overlap window + idempotent update 通过 |
| Review | 全流程 demo 测试 + GPT review | Phase 1-4 | ⬜ Pending | User + GPT | 2026-04-11 | 2026-04-11 | 端到端 smoke 通过 |

## 节奏规则

1. 先锁 contract，再写 crawler 和 graph，避免后面在 ID 约定上返工。
2. `update` 不与 Phase 1 并行承诺；必须等 full crawl 和 graph 的 schema 稳定后再做。
3. 每个 Phase 完成时都要过对应 Gate，没过就不推进下一个 Phase。

## Phase 0 细节

| Step | 任务 | 状态 |
|------|------|------|
| 0.1 | 锁定 CSV schema：`paper_id`、`arxiv_id`、`s2_paper_id` | ⬜ |
| 0.2 | 锁定 full/update 写入策略（人工列保留） | ⬜ |
| 0.3 | 准备 mixed-source fixture 与 expected CSV | ⬜ |
| 0.T | Gate 0：contract 定稿 | ⬜ |

## Phase 1 细节

| Step | 任务 | 状态 |
|------|------|------|
| 1.1 | 配置加载 + 状态管理（`config.yaml`, `crawl-state.json`） | ⬜ |
| 1.2 | arXiv 爬取（复用 `arxiv_fetch.py`） | ⬜ |
| 1.3 | Semantic Scholar 爬取（复用 `semantic_scholar_fetch.py`） | ⬜ |
| 1.4 | arXiv 论文补充 S2 字段（`citation_count`, `venue`, `s2_paper_id`） | ⬜ |
| 1.5 | 去重 + 记录合并（`arxiv_id > doi > s2_paper_id`） | ⬜ |
| 1.6 | 关键词排序 | ⬜ |
| 1.7 | merge-safe CSV 写入（full / update 都保留人工列） | ⬜ |
| 1.8 | 状态更新（canonical `paper_id`） | ⬜ |
| 1.T | Gate 1：fixture 测试 + rerun 保留人工列 | ⬜ |

## Phase 2 细节

| Step | 任务 | 状态 |
|------|------|------|
| 2.1 | `survey-crawl.md`：生成或复用配置，触发 full crawl | ⬜ |
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
| 3.6 | 统计摘要 `stats.md`（含 unresolved 统计） | ⬜ |
| 3.7 | `survey-graph.md` skill | ⬜ |
| 3.T | Gate 3：mixed-ID 样本出图验证 | ⬜ |

## Phase 4 细节

| Step | 任务 | 状态 |
|------|------|------|
| 4.1 | `survey_crawler.py` update 模式（含 overlap window） | ⬜ |
| 4.2 | `survey-update.md` skill | ⬜ |
| 4.3 | 同一窗口重复 update 的幂等验证 | ⬜ |
| 4.T | Gate 4：增量更新验证通过 | ⬜ |

## 风险焦点

| 风险 | 影响 | 应对 |
|------|------|------|
| mixed ID 约定不清 | graph / update 阶段返工 | Phase 0 先锁 contract |
| full crawl 覆盖人工列 | 用户筛选结果丢失 | merge-safe 写入 |
| S2 日期过滤粗粒度 | update 漏论文或重复追加 | overlap window + client-side 过滤 |

## 变更记录

| 日期 | 变更 |
|------|------|
| 2026-04-07 | 项目启动，方案拆分为 4 个 Phase |
| 2026-04-07 | timeline 修订为带 Gate 的建议排期，并新增 Phase 0 contract baseline |
