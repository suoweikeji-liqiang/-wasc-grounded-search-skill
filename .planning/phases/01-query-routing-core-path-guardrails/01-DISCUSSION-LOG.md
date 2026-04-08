# Phase 1: Query Routing & Core Path Guardrails - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-08
**Phase:** 1-Query Routing & Core Path Guardrails
**Areas discussed:** 混合题处理, 分型阈值, 可观测输出, 低置信度兜底

---

## 混合题处理

### Question 1: mixed query 默认应该怎么走？

| Option | Description | Selected |
|--------|-------------|----------|
| 主+辅双路 | 先定一个主路由，再只补一个次路由。覆盖够用，也最符合当前预算/稳定性目标。 | ✓ |
| 三路并发 | policy / industry / academic 三路都跑，召回最全，但最容易拉高延迟和后续上下文成本。 | |
| 单主路由 | 无论多混合都只保留一个主路由，最省资源，但容易漏掉关键补充证据。 | |

**User's choice:** 主+辅双路
**Notes:** Mixed queries should stay cost-controlled and deterministic instead of expanding to full fan-out.

### Question 2: 什么时候启用补充路由？

| Option | Description | Selected |
|--------|-------------|----------|
| 显式跨域触发 | 只有查询里出现明确跨域意图时才加补充路由，比如“政策影响行业”“论文与监管对比”。这样最稳。 | ✓ |
| 低置信度也触发 | 只要主路由分数不够高，也加一个补充路由，召回更保守，但 mixed 会变多。 | |
| 判 mixed 即触发 | 一旦判成 mixed，就固定带一个补充路由，不再细分触发条件。 | |

**User's choice:** 显式跨域触发
**Notes:** Low confidence alone should not be enough to widen the route plan.

---

## 分型阈值

### Question 1: Phase 1 的分型机制先锁哪种？

| Option | Description | Selected |
|--------|-------------|----------|
| 规则优先 | 先用确定性规则：关键词/实体/语义线索命中即分到 policy、industry、academic；只有明确跨域才 mixed。最容易验证和复现。 | ✓ |
| 规则+轻模型 | 先规则分型，再允许轻量模型在边界样本上改判。更灵活，但会把 Phase 1 变复杂。 | |
| 模型优先 | 直接用模型分型。实现快，但不利于可解释和稳定复现。 | |

**User's choice:** 规则优先
**Notes:** Determinism and repeatability matter more than classifier flexibility in this phase.

### Question 2: 单标签冲突时，默认优先级怎么定？

| Option | Description | Selected |
|--------|-------------|----------|
| Academic>Policy>Industry | 学术信号最强时优先 academic；政策词命中时优先 policy；其余默认 industry。适合当前三类题差异。 | |
| Policy>Academic>Industry | 政策信号最强时优先 policy；学术其次；其余 industry。更偏向权威源，但可能压住学术题。 | ✓ |
| 冲突即 mixed | 不设固定优先级，冲突就直接 mixed。更保守，但 mixed 数量会更多。 | |

**User's choice:** Policy>Academic>Industry
**Notes:** Policy should win ambiguous single-label conflicts unless the query is clearly cross-domain.

---

## 可观测输出

### Question 1: Phase 1 对外默认暴露到什么粒度？

| Option | Description | Selected |
|--------|-------------|----------|
| 标签+信源族 | 返回 route label + source families。已经满足“可观察”，同时不会过早把解释层做重。 | ✓ |
| 标签+信源族+理由 | 再加一段简短理由，比如“命中政策词+年份”。更易调试，但输出 contract 更重。 | |
| 只返标签 | 只返回 route label。最轻，但不够支撑 ROUT-02 的可观察性。 | |

**User's choice:** 标签+信源族
**Notes:** Observability should be sufficient for verification without adding a heavier explanation layer.

### Question 2: 这些路由信息主要放在哪里？

| Option | Description | Selected |
|--------|-------------|----------|
| 结构化字段 | 把路由信息放进结构化响应字段，后续测试和 planner 都更容易依赖。 | ✓ |
| 仅内部日志 | 只打日志，不出现在响应里。实现轻，但用户侧不可观察。 | |
| 响应+日志 | 同时放响应和日志。更完整，但现在比 Phase 1 目标略重。 | |

**User's choice:** 结构化字段
**Notes:** The route contract should be externally visible, not just an internal debugging tool.

---

## 低置信度兜底

### Question 1: 分型低置信度时，主链路默认怎么兜底？

| Option | Description | Selected |
|--------|-------------|----------|
| 默认 industry | 分型不够稳时默认走 industry，并保留轻量通用 web 检索。实现最简单，但可能偏离“route-first”的可解释性。 | |
| 升级 mixed | 分型不够稳时直接升成 mixed，仍保持主+辅双路。更保守，也更符合前面 mixed 设计。 | ✓ |
| 返回不足路由 | 直接返回 insufficient-route，不继续主链路。最严格，但会损失 Phase 1 端到端成功率。 | |

**User's choice:** 升级 mixed
**Notes:** The main path should keep moving instead of failing closed when the classifier is uncertain.

### Question 2: 对特别短、信息不足的问句，单独怎么处理？

| Option | Description | Selected |
|--------|-------------|----------|
| 短问句也 mixed | 对很短或上下文不足的问题，也沿用“升级 mixed”策略，保持一套规则。 | ✓ |
| 短问句默认 industry | 短问句单独走默认 industry，避免 mixed 过多。 | |
| 要求补充信息 | 短问句直接要求用户补充信息。更严谨，但不利于 benchmark 流程。 | |

**User's choice:** 短问句也 mixed
**Notes:** Short queries should follow the same fallback rule to avoid special-case routing behavior.

---

## Claude's Discretion

- Exact rule expressions, match scoring, and threshold tuning inside the rule-first classifier
- Final response schema field names for route metadata
- Internal logging shape beyond the user-visible route contract

## Deferred Ideas

- Full three-way mixed routing fan-out
- Model-assisted classifier fallback in Phase 1
- Insufficient-route refusal state as the default low-confidence behavior
