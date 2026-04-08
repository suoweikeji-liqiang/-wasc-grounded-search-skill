# Project Research Summary

**Project:** WASC 低成本高精度搜索 Skill  
**Domain:** 竞赛型路由搜索与证据化回答（政策 / 行业 / 学术）  
**Researched:** 2026-04-08  
**Confidence:** MEDIUM-HIGH

## Executive Summary

这是一个竞赛约束下的检索-生成系统，而不是通用聊天产品。研究结论高度一致：要同时拿到准确度、全面度、时延、稳定性与 token 成本分，必须采用确定性流水线——**题型分流 → 信源路由 → 并发检索 → 去重重排 → 证据压缩 → 单次合成 → 引用校验**。

推荐路径是轻量、可审计、可复现：Python 3.12 + FastAPI/MCP、httpx 并发检索、trafilatura 清洗、BM25/RRF 融合、MiniMax-M2.7 单次结构化合成、强 schema 输出。核心风险是：不分流导致系统性失配、引用有链接但无版本/辖区/片段绑定、以及盲目堆上下文导致 token 与稳定性崩坏。缓解靠路由规则、evidence schema、硬预算和 deterministic fallback FSM。

## Key Findings

### Recommended Stack
- **Python 3.12.x**：生态最全，竞赛环境友好
- **FastAPI 0.135.2 + Uvicorn 0.44.0**：稳定 API / Skill 暴露
- **mcp 1.27.0**：对齐 MCP Skill 形态
- **httpx 0.28.1 + tenacity 9.1.4**：并发检索与重试治理
- **trafilatura 2.0.0**：正文抽取降噪
- **rank-bm25 0.2.2 + RRF**：低成本可解释重排
- **MiniMax-M2.7（单次）**：最终合成，控制 token 与延迟

### Expected Features
**Must-have**
- 查询分型（政策 / 行业 / 学术 / 混合）
- 信源路由与可信度分层
- 多源并发检索 + 超时控制 + 异常隔离
- 去重 + 轻量重排 + Top-K 预算裁剪
- 结构化输出 + 逐结论引用绑定 + 不确定项
- 时效 / 版本 / 辖区显式提示

**Should-have**
- 受控查询扩展（3–5 子查询）
- 跨源融合排序（RRF）
- 冲突检测与证据分歧提示
- 置信度分层与缺口说明
- 查询规范化缓存与结果缓存

**Defer**
- Playwright / Selenium 作为默认主路径
- 多轮自我讨论式 Agent 长链
- 多大模型串联与大而全产品化能力

### Architecture Approach
分层解耦架构：API/校验层、编排策略层、检索执行层、排序压缩层、合成校验层、缓存观测层。
关键模式：**Route-then-Retrieve**、**Deadline-driven orchestration**、**Deterministic fallback FSM**。
关键边界：API 不直连 provider；检索层不直连生成层；生成层必须经过 citation checker fail-closed。

### Critical Pitfalls
1. 三类题走单一路由 → 必须题型分桶 + 专属信源策略
2. 政策“有链接无版本/辖区” → 强制 authority / jurisdiction / effective_date / version
3. 学术 preprint / 正式版不归并 → DOI / arXiv / canonical key 归并
4. 盲目堆上下文 → 双层压缩 + 硬 token budget
5. 只看单次最优跑分 → 10×5 稳定性基线（成功率 / P95 / token 方差）

## Implications for Roadmap

### Phase 1: Query Routing Baseline + Eval Protocol
- 题型判定、信源白黑名单、10×5 稳定性基线
- 先把路由正确性和评测协议打牢

### Phase 2: Evidence Schema + Source Adapters + Normalization
- 适配器、证据 schema、政策版本校验、学术 canonical 归并
- 先把证据可追溯与元数据正确性打牢

### Phase 3: Ranking / Compression + Grounded Synthesis
- 去重、BM25 / RRF、Top-K 片段预算、单次合成、citation checker
- 平衡精度、token 与易用性

### Phase 4: Reliability Engineering + Fallback FSM
- 预算控制、重试 / 熔断、降级状态机、P95 / P99 门禁
- 直接服务稳定性与可运行性评分

### Phase 5: Controlled Differentiators
- 查询扩展、冲突检测、置信度分层、缓存优化
- 仅在主链路稳定后加竞争增强能力

## Confidence Assessment

| Area | Confidence | Notes |
|---|---|---|
| Stack | HIGH | 主要基于官方文档 / PyPI，版本与兼容性明确 |
| Features | MEDIUM-HIGH | 与竞赛目标强一致，差异化项需实测 |
| Architecture | MEDIUM-HIGH | 模式成熟，具体阈值需压测校准 |
| Pitfalls | MEDIUM | 上下文支撑强，部分外部论文证据级别偏中低 |

**Overall confidence:** MEDIUM-HIGH

### Gaps to Address
- 评分细则权重未完全量化（需建立代理指标）
- 外部源限流 / SLA 波动需 provider 级压测
- 政策版本 / 辖区规则库需迭代扩充
- preprint → published 映射漏检率需抽样校验
- 多语种术语扩展收益需消融验证

## Sources
- `D:\study\WASC\.planning\research\STACK.md`
- `D:\study\WASC\.planning\research\FEATURES.md`
- `D:\study\WASC\.planning\research\ARCHITECTURE.md`
- `D:\study\WASC\.planning\research\PITFALLS.md`
