# Phase 2: Multi-Source Retrieval by Domain - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md — this log preserves the alternatives considered.

**Date:** 2026-04-11
**Phase:** 02-multi-source-retrieval-by-domain
**Areas discussed:** 信源组合, 并发与超时, 降级与回退, 领域优先级

---

## 信源组合

| Option | Description | Selected |
|--------|-------------|----------|
| 稳妥首发 | policy 官方优先 + academic 双源 + industry 轻组合 + mixed 主路全跑补路单点 | ✓ |
| 政策更重 | 先把 policy 做最强，其他路线保守 | |
| 学术更重 | 先把 academic 做最强，其他路线保守 | |
| 你直接定 | 用户自行指定每个 domain 的首发源组 | |

**User's choice:** 稳妥首发
**Notes:** 用户随后进一步锁定：policy=官方优先+限定补位；academic=Semantic Scholar+arXiv；industry=ddgs 分层轻组合；mixed=主路全跑+补路单点。

### 信源组合 / policy 起步

| Option | Description | Selected |
|--------|-------------|----------|
| 官方优先+限定补位 | 主路径信官方/监管/标准源，失败或不足时用限定官方域名 web 搜索补位 | ✓ |
| 纯官方源 | 只接官方/监管/标准源，不做 web 补位 | |
| 官方+通用搜索 | 官方和通用 web 同时跑 | |

**User's choice:** 官方优先+限定补位
**Notes:** 目标是维持可信性和稳定性，不让 unrestricted general web 进入 policy 主路径。

### 信源组合 / academic 起步

| Option | Description | Selected |
|--------|-------------|----------|
| 语义学术双源 | Semantic Scholar + arXiv 作为第一版主干 | ✓ |
| 三源扩展 | Semantic Scholar + arXiv + Crossref/OpenAlex | |
| 只做学术元数据 | 先只做单一 scholarly metadata 源 | |

**User's choice:** 语义学术双源
**Notes:** 第一版保持 scholarly stack 精简，先不扩展到更大的 provider mesh。

### 信源组合 / industry 起步

| Option | Description | Selected |
|--------|-------------|----------|
| 分层轻组合 | ddgs 取候选，再按官方/协会/可信新闻/通用 web 分层 | ✓ |
| 搜索优先 | 以通用 web 搜索为主，可信站只做少量加权 | |
| 商业API优先 | 用商业搜索 API 做行业主干 | |

**User's choice:** 分层轻组合
**Notes:** 用户优先选择轻路径，不引入商业 API 作为第一版主干。

### 信源组合 / mixed 处理

| Option | Description | Selected |
|--------|-------------|----------|
| 主路全跑+补路单点 | primary 跑完整首发源组，supplemental 只跑一个最强补位源 | ✓ |
| 双路对称 | primary 和 supplemental 都跑完整源组 | |
| 补路只留后备 | 默认只跑 primary，弱时再触发 supplemental | |

**User's choice:** 主路全跑+补路单点
**Notes:** 与 Phase 1 的 mixed 约束保持一致：primary 主导、supplemental 只补视角。

---

## 并发与超时

| Option | Description | Selected |
|--------|-------------|----------|
| 硬预算型 | 每源约 3s + retrieval 总 deadline + 到点收束已有结果 | ✓ |
| 稍宽松型 | 每源 4-5s，尽量多等一点结果 | |
| 按 domain 区分 | 不同 domain 不同 timeout / deadline | |
| 你自定义 | 用户直接指定预算 | |

**User's choice:** 硬预算型
**Notes:** 明确偏向比赛友好的稳定、低尾延迟预算模型。

### 并发与超时 / 总时限

| Option | Description | Selected |
|--------|-------------|----------|
| 固定总deadline | retrieval stage 有固定总时限 | ✓ |
| 只控每源 | 只使用 per-source timeout | |
| 按领域分时限 | 各领域用不同总体时限 | |

**User's choice:** 固定总deadline
**Notes:** Retrieval 不能只靠自然结束，必须有统一收束边界。

### 并发与超时 / 请求发射策略

| Option | Description | Selected |
|--------|-------------|----------|
| 全发+全局上限 | 当前 plan 内 source 一起发出，用全局 semaphore 限制并发 | ✓ |
| 分批发 | 先发主源，再发次源 | |
| 按领域分并发 | 各领域各自一套并发策略 | |

**User's choice:** 全发+全局上限
**Notes:** 第一版避免 staged retrieval，直接走统一 fan-out。

### 并发与超时 / 慢源处理

| Option | Description | Selected |
|--------|-------------|----------|
| 到点即收束 | deadline 到时直接丢弃未返回结果 | ✓ |
| 允许短宽限 | 少量慢源允许再等一下 | |
| 高优先源例外 | 只有高优先源允许宽限 | |

**User's choice:** 到点即收束
**Notes:** 不给慢源默认 grace period，保护稳定性和 P95。

---

## 降级与回退

| Option | Description | Selected |
|--------|-------------|----------|
| 确定性降级链 | source 失败/不足时按预定义链路降级，仍返回结构化结果 | ✓ |
| 尽量补全型 | 失败后做更多补查/替代查询 | |
| 极简失败跳过型 | 只忽略失败源，不走明确备源链 | |
| 你自定义 | 用户逐类指定异常处理 | |

**User's choice:** 确定性降级链
**Notes:** 用户明确不要开放式智能恢复，优先 deterministic FSM。

### 降级与回退 / 空结果

| Option | Description | Selected |
|--------|-------------|----------|
| 视作软失败 | 正常返回但无结果时进入备源/已有结果路径 | ✓ |
| 改写后重试 | 立刻改写 query 再查一次 | |
| 直接忽略 | 不触发任何补位 | |

**User's choice:** 视作软失败
**Notes:** 空结果不会触发 query rewrite retry，避免 Phase 2 scope 膨胀。

### 降级与回退 / 429

| Option | Description | Selected |
|--------|-------------|----------|
| 直接切备源 | rate-limit 立刻切到预定义 backup source | ✓ |
| 短退避一次 | 先短暂 backoff 再切备源 | |
| 只记失败 | 不补位，只记录失败 | |

**User's choice:** 直接切备源
**Notes:** 主路径不等待长退避，优先稳定性。

### 降级与回退 / 全失败

| Option | Description | Selected |
|--------|-------------|----------|
| 结构化失败结果 | 返回 retrieval failure/gaps 的结构化 outcome | ✓ |
| 直接报错 | 抛 API error 给上层处理 | |
| 再加最终兜底 | 触发更宽松的最终 web fallback | |

**User's choice:** 结构化失败结果
**Notes:** 这会给后续 Phase 4 的 structured outcome 明确输入边界。

---

## 领域优先级

| Option | Description | Selected |
|--------|-------------|----------|
| 规则优先型 | policy / academic / industry 各自按 domain trust rules 排序 | ✓ |
| 相关性优先型 | 所有 domain 先按 relevance，再轻微加 authority/recency | |
| 强时效型 | 更重视 recency，尤其 policy/industry | |
| 你自定义 | 用户逐域指定 priority | |

**User's choice:** 规则优先型
**Notes:** 用户希望 domain-aware priority 是显式规则，不藏在通用 relevance 分数里。

### 领域优先级 / policy 排位

| Option | Description | Selected |
|--------|-------------|----------|
| 官方绝对优先 | 官方/监管/标准原文始终压过二手解读 | ✓ |
| 官方优先但可让位 | 只有相关性接近时才优先官方 | |
| 相关性优先 | relevance 先行，官方只轻微加权 | |

**User's choice:** 官方绝对优先
**Notes:** 权威原文优先级是硬规则。

### 领域优先级 / academic 排位

| Option | Description | Selected |
|--------|-------------|----------|
| 只收学术源 | 只有 scholarly source 进入 academic 主候选 | ✓ |
| 学术优先+网页尾补 | 允许少量普通网页低权进入尾部 | |
| 统一收录 | 所有结果都进统一排序 | |

**User's choice:** 只收学术源
**Notes:** 第一版 academic 主候选不纳入普通网页结果。

### 领域优先级 / mixed 排位

| Option | Description | Selected |
|--------|-------------|----------|
| 主路主导 | primary route 主导排序，supplemental 只补证/补视角 | ✓ |
| 双路对称 | 两路对称参与排序 | |
| 动态主导 | 按每次结果动态决定谁主导 | |

**User's choice:** 主路主导
**Notes:** 继续延续 Phase 1 的 primary-dominant mixed 策略。

### 领域优先级 / industry 排位

| Option | Description | Selected |
|--------|-------------|----------|
| 可信层级优先 | company official > association > trusted news > general web | ✓ |
| 相关性优先 | 先 relevance，再看可信层级 | |
| 时效优先 | 新鲜度高于可信层级 | |

**User's choice:** 可信层级优先
**Notes:** recency / relevance 只在同一可信层级内再比较。

---

## Claude's Discretion

- 精确 semaphore 数值
- retrieval 总 deadline 的具体秒数
- adapter 接口细节与内部错误码设计
- 每个 tier 内部的具体打分公式

## Deferred Ideas

- industry 商业搜索 API 主干
- academic 首发即接 Crossref/OpenAlex
- 空结果时 query rewrite retry
- mixed 双路完整对称 fan-out
- 最终重型 fallback 路径
