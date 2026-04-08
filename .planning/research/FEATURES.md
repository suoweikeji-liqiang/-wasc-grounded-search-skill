# Feature Landscape

**Domain:** WASC 竞赛型低成本高精度搜索 Skill（政策/行业/学术三类查询）  
**Researched:** 2026-04-07  
**Overall confidence:** MEDIUM-HIGH（竞赛规则与项目上下文高置信；部分“2026生态最佳实践”为中置信）

## Table Stakes（不做就会明显掉分/掉队）

| Feature | Why Expected | Complexity | Notes |
|---|---|---|---|
| 查询分型（政策/行业/学术/混合） | 官方测试题就覆盖三类；不分型会系统性失配 | Low | 先规则路由，避免上来就LLM分类耗token |
| 信源路由与可信度分层 | 评分看准确度+全面度+来源；“去哪找”比“搜多少”更关键 | Med | 政策优先官方原文；学术优先结构化学术源；行业多源聚合 |
| 多源并发检索+超时控制 | 请求时间/可运行性/稳定性都看平均表现 | Med | 并发+每源超时+异常隔离，防止单点拖垮 |
| 结果去重+轻量重排 | 不去重不重排会浪费上下文并拉低精度 | Med | URL/标题/摘要去重 + BM25/RRF/轻量rerank |
| 上下文预算控制（Top-K裁剪+片段截断） | token评分独立计分；成本必须可控 | Low | 先在检索层压缩，不把脏长文本直接喂模型 |
| 强制引用与证据绑定输出 | 准确度维度明确看来源链接与幻觉控制 | Low | 关键结论必须带来源编号与链接 |
| 结构化输出模板 | 易用性和全面度评分受输出组织影响大 | Low | 固定字段：结论/要点/来源/时间版本/不确定点 |
| 失败降级链路（fallback） | 稳定性按重复运行统计，必须抗抖动 | Med | 源失败→备源；重排失败→基础排序；仍返回“部分可用结果” |
| 结果时效/版本提示 | 政策和行业信息强时效，旧版本误导严重 | Med | 输出中显式标注发布日期/版本/地域适用性 |

## Differentiators（能拉开与“普通搜索封装”差距）

| Feature | Value Proposition | Complexity | Notes |
|---|---|---|---|
| 查询扩展 + 多视角召回（受控3-5子查询） | 提升召回全面性，同时可控成本 | Med | 子查询数量上限必须硬控，防冗余 |
| 跨源融合排序（RRF/融合打分） | 同时兼顾多源、多子查询一致性 | Med | 对政策/行业/学术混合题尤有效 |
| 题型特化摘要器（policy/industry/academic模板） | 同样证据下，回答可用性更高、更像“专业交付” | Med | 例如政策题强制输出“机构+条款+版本” |
| 冲突检测与“证据分歧”提示 | 在行业和混合题上显著降低误判 | Med | 多来源冲突时不给单一武断结论 |
| 低成本缓存（查询规范化+结果缓存） | 重复题/近似题显著降时延和token | Med | 对50次稳定性跑分非常友好 |
| 置信度分层（高/中/低）+ 缺口说明 | 评委更易判断“诚实性与可复核性” | Low | “来源不足”比编造更高分 |
| 学术源结构化优先（Semantic Scholar/OpenAlex/arXiv/Crossref） | 学术题命中率和可引用性显著提升 | Med | 优先元数据+摘要，不做重爬全网 |

## Anti-Features（应明确不做）

| Anti-Feature | Why Avoid | What to Do Instead |
|---|---|---|
| 浏览器自动化作为默认主路径（Playwright-first） | 慢、重、脆弱，拉低稳定性与时间分 | 仅作为极少数兜底，不进入主链路 |
| 聊天型长链路Agent（多轮自我讨论） | token与时延不可控，波动大 | 单轮受控流水线：检索→筛选→结构化生成 |
| “全量抓取后再让LLM自己挑” | 成本高且噪声大，易幻觉 | 检索层先做去重/筛选/压缩 |
| 无来源结论或仅给裸链接 | 准确度和易用性都会丢分 | 结论-证据一一绑定（引用编号） |
| 追求“全功能产品化” | 偏离竞赛目标，开发风险高 | 只做 benchmark 相关能力 |
| 复杂模型堆叠（多大模型串联） | 成本、稳定性、调试复杂度飙升 | 统一模型+轻量检索重排 |

## Feature Dependencies

```text
查询分型 → 信源路由 → 多源并发检索
多源并发检索 → 去重/重排 → 上下文预算控制 → 结构化生成
信源路由 + 时效/版本识别 → 高可信引用输出
去重/重排 → 冲突检测 → 置信度分层
主路径稳定后 → 缓存优化（加速与降本）
```

## MVP Recommendation（竞赛导向）

优先做（MVP）：
1. 查询分型 + 信源路由（政策/行业/学术）
2. 多源并发检索 + 去重 + 轻量重排
3. 结构化输出 + 强制引用 + 不确定性声明

第一批可延期：
- 查询扩展（多视角）
- 冲突检测与证据分歧解释
- 缓存与进一步token压缩策略

明确后置：
- 浏览器重路径常态化
- 泛化“聊天Agent能力”
- 大而全产品功能

## 结论（一句话）

这类 Skill 的胜负手不是“会不会搜”，而是**能否在受限资源下稳定执行“分型路由→可信检索→压缩重排→证据化结构输出”**，并且把重路径严格后置。

---

Sources:
- [MiniMax API Overview](https://platform.minimax.io/docs/api-reference/api-overview)
- [MiniMax Tool Use & Interleaved Thinking](https://platform.minimax.io/docs/guides/text-m2-function-call)
- [MiniMax Text Generation Intro](https://platform.minimax.io/docs/api-reference/text-intro)
- [Semantic Scholar API](https://www.semanticscholar.org/product/api)
- [Semantic Scholar Graph API Docs](https://api.semanticscholar.org/api-docs/graph)
- [OpenAlex API Introduction](https://developers.openalex.org/api-reference/introduction)
- [OpenAlex Searching Guide](https://developers.openalex.org/guides/searching)
- [Crossref REST API Docs](https://www.crossref.org/documentation/retrieve-metadata/rest-api/)
- [arXiv API Access](https://info.arxiv.org/help/api/index.html)
- [arXiv API User Manual](https://info.arxiv.org/help/api/user-manual.html)
- [WASC 赛事规则（你提供的本地资料）](D:\study\WASC\比赛.txt)
