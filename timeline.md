# Survey Pipeline — Timeline

## 项目启动：2026-04-07

| Phase | 内容 | 状态 | 负责人 | 开始 | 完成 |
|-------|------|------|--------|------|------|
| Phase 1 | survey_crawler.py 爬取编排器 | ⬜ Pending | Claude | - | - |
| Phase 2 | survey-crawl.md + survey-filter.md skills | ⬜ Pending | Claude | - | - |
| Phase 3 | citation_graph.py + survey-graph.md | ⬜ Pending | Claude | - | - |
| Phase 4 | survey-update.md 增量更新 | ⬜ Pending | Claude | - | - |
| Review | 全流程 demo 测试 + GPT review | ⬜ Pending | User + GPT | - | - |

## Phase 1 细节

| Step | 任务 | 状态 |
|------|------|------|
| 1.1 | 配置加载 + 状态管理（config.yaml, crawl-state.json） | ⬜ |
| 1.2 | arXiv 爬取（复用 arxiv_fetch.py） | ⬜ |
| 1.3 | Semantic Scholar 爬取（复用 semantic_scholar_fetch.py） | ⬜ |
| 1.4 | S2 引用数补充（arXiv 论文补充 citation_count） | ⬜ |
| 1.5 | 去重 + 合并 | ⬜ |
| 1.6 | 关键词排序 | ⬜ |
| 1.7 | CSV 写入（full + update 模式） | ⬜ |
| 1.8 | 状态更新 | ⬜ |
| 1.T | Phase 1 单元测试验证 | ⬜ |

## Phase 2 细节

| Step | 任务 | 状态 |
|------|------|------|
| 2.1 | survey-crawl.md skill | ⬜ |
| 2.2 | survey-filter.md skill | ⬜ |
| 2.T | Phase 2 端到端验证 | ⬜ |

## Phase 3 细节

| Step | 任务 | 状态 |
|------|------|------|
| 3.1 | 读取 filtered CSV | ⬜ |
| 3.2 | S2 引用关系获取 + 缓存 | ⬜ |
| 3.3 | networkx 有向图构建 | ⬜ |
| 3.4 | matplotlib 渲染 | ⬜ |
| 3.5 | DOT 文件输出 | ⬜ |
| 3.6 | 统计摘要 stats.md | ⬜ |
| 3.7 | survey-graph.md skill | ⬜ |
| 3.T | Phase 3 验证 | ⬜ |

## Phase 4 细节

| Step | 任务 | 状态 |
|------|------|------|
| 4.1 | survey_crawler.py update 模式 | ⬜ |
| 4.2 | survey-update.md skill | ⬜ |
| 4.T | Phase 4 增量更新验证 | ⬜ |

## 变更记录

| 日期 | 变更 |
|------|------|
| 2026-04-07 | 项目启动，方案拆分为 4 个 Phase |
