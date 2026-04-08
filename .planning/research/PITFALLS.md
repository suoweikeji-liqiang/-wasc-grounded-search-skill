# Domain Pitfalls

**Domain:** WASC 比赛型低成本高精度搜索 Skill（政策法规 / 行业信息 / 学术文献）
**Researched:** 2026-04-07
**Confidence:** MEDIUM（核心结论由项目上下文+多源资料支持；部分前沿论文结论仍需实测验证）

## Critical Pitfalls

### Pitfall 1: 把“三类题”当成单一路由（不做题型分流）

**What goes wrong:**
政策、行业、学术查询走同一检索链，导致：
- 政策题命中二手解读而非原始法规；
- 学术题命中普通网页而非论文元数据源；
- 行业题来源层级混乱，结论“看起来全，实则不可信”。

**Why it happens:**
为了快速上线，团队先做“一个通用搜索+总结”，忽略 benchmark 三类题分布与评分差异。

**Prevention:**
- Phase 1 明确题型判定规则（policy / industry / academic / mixed）与冲突优先级。
- 每类题绑定首选/次选/降权信源表（白名单+黑名单）。
- 评测按题型分 bucket 出分，禁止只看总均分。

**Detection / Warning signs:**
- 学术题来源中学术数据库占比低；
- 政策题输出无发布机构/版本/生效时间；
- 同一问题多次运行来源类型波动大。

**Phase to address:**
Phase 1（Query Typing & Routing Baseline）

---

### Pitfall 2: 政策法规“引用了链接”但没做版本与辖区校验

**What goes wrong:**
答案看似有来源，但引用的是过期版本、地方版本、解读稿或转载页，导致事实“半真半假”。

**Why it happens:**
很多实现只校验“有 URL”，不校验：
- 发布主体权威性；
- 文档版本/发布日期/修订状态；
- 适用辖区（国家/省市/行业监管口径）。

**Prevention:**
- 证据对象强制结构化：`authority`, `jurisdiction`, `effective_date`, `version`, `doc_type(original/interpreted)`。
- 政策题默认“原文优先”，二手解读仅作补充且显式标注。
- 对同名政策执行“最新版本冲突检查”。

**Detection / Warning signs:**
- 结论中缺“适用范围/生效时间”字段；
- 引用集中在资讯站、博客、聚合站；
- 同题不同次输出互相矛盾（常见于版本混用）。

**Phase to address:**
Phase 2（Evidence Schema & Source Trust Rules）

---

### Pitfall 3: 学术检索未做“preprint 与正式发表合并”导致错引/重引

**What goes wrong:**
把 arXiv 预印本与期刊正式版当两篇；或引用 metadata 不一致的条目，造成“全面度看似高、准确度下降”。

**Why it happens:**
学术搜索通常跨源（arXiv/Crossref/Scholar），若无 canonical id（DOI/ArXiv ID）对齐和版本归并，极易重复与错配。

**Prevention:**
- 学术记录标准化键：`doi || arxiv_id || title+first_author+year`。
- 建立 preprint→published 解析链，优先返回正式版并保留预印本关系。
- 输出层增加“证据级别”（preprint / peer-reviewed / survey）。

**Detection / Warning signs:**
- 参考文献列表出现高相似标题重复；
- DOI 可解析但题名/作者不一致；
- “最新研究”回答中预印本占比异常高且未标注。

**Phase to address:**
Phase 2（Academic Metadata Normalization）

---

### Pitfall 4: 为了“全面度”盲目加长上下文，拖垮 tokens 与稳定性

**What goes wrong:**
Top-N 拉太多、全文塞模型，导致：
- token 飙升；
- 响应超时；
- 重复运行波动加大；
- 反而更容易幻觉（模型在噪声中拼接）。

**Why it happens:**
误把“更多网页/更长上下文”当作全面度提升手段，而不是“高价值证据覆盖”。

**Prevention:**
- 双层压缩：检索层去重/降噪 + 证据层段落级 rerank（只保留 Top-K 片段）。
- 为每类题设置 token budget（输入预算硬阈值）。
- 输出必须有“不确定点”字段，避免靠猜测补全。

**Detection / Warning signs:**
- token 与延迟呈线性增长，质量却无显著提升；
- 50 次稳定性测试中方差增大；
- 引用数量增加但信息冲突也增加。

**Phase to address:**
Phase 3（Compression & Token Budget Enforcement）

---

### Pitfall 5: 用单次跑分优化，忽视“重复运行稳定性”维度

**What goes wrong:**
一次结果很好，但 50 次压测中失败/波动明显，直接丢稳定性与可运行性分。

**Why it happens:**
只做离线“best run”评估，不做重复运行、超时、失败回退统计；未记录外部搜索源波动影响。

**Prevention:**
- 评测脚本固定：10 题 × 5 次，记录成功率、P95 延迟、token 方差、答案差异度。
- 引入 deterministic controls：超时阈值、固定重试策略、固定候选上限。
- 设置降级链：主源失败→备源→最小可答复模板。

**Detection / Warning signs:**
- 同 query 多次运行引用集合 Jaccard 低；
- 时延偶发尖峰；
- 外部源轻微抖动就触发超时或空结果。

**Phase to address:**
Phase 1/4（Benchmark Harness + Reliability Engineering）

---

### Pitfall 6: 评测数据与系统策略“相互污染”（benchmark overfitting / leakage）

**What goes wrong:**
针对影子题写死规则、缓存污染评测，线上看似高分，换题即崩；可迁移性差。

**Why it happens:**
比赛压力下容易把“调参到题”当“能力提升”，缺少严格 train/eval 分离与盲测集。

**Prevention:**
- Shadow benchmark 分层：dev / tune / blind 三套，禁止交叉回写。
- 缓存键纳入时间窗与源版本，评测时可禁用热缓存做冷启动对比。
- 每次优化只改一个变量，记录因果（ablation）。

**Detection / Warning signs:**
- 开发集分数持续涨，盲测不涨或下降；
- 替换 query 表述后性能骤降；
- 缓存命中率异常高但真实检索质量不变。

**Phase to address:**
Phase 1（Evaluation Protocol & Anti-Leakage Rules）

---

### Pitfall 7: “有引用”但不可追溯（引用断链、片段不对应）

**What goes wrong:**
回答附了链接，但无法定位支撑该结论的原文片段，评审会判“可追溯性不足”。

**Why it happens:**
生成阶段只保留 URL，不保留证据片段、抓取时间、标题快照；站点更新后引用漂移。

**Prevention:**
- 证据最小单元必须保存：title/url/quote/retrieved_at/hash。
- 输出中每个关键事实绑定至少一个 quote-level citation。
- 对高权重事实做二次校验（quote 与结论语义一致）。

**Detection / Warning signs:**
- 点击链接找不到对应说法；
- 同 URL 内容更新后结论失效；
- 引用仅在段尾集中出现，未与事实逐条绑定。

**Phase to address:**
Phase 2/3（Evidence Packaging & Grounded Generation）

---

### Pitfall 8: 忽视跨语种与术语歧义（尤其政策/产业中英混合）

**What goes wrong:**
中文问题检索英文源或反之时，术语映射失败，召回不足或召回偏题。

**Why it happens:**
未做 query expansion（同义词、缩写、法规正式名称）；只靠原始 query 关键词直搜。

**Prevention:**
- 建立轻量术语扩展表（中英缩写、政策别名、机构别名）。
- 在检索前生成 2-4 条受控改写 query（而非无限扩写）。
- 对 mixed query 先抽“主语+约束词（时间/地区/版本）”再检索。

**Detection / Warning signs:**
- 中文学术题几乎只回中文博客；
- 行业题英文缩写导致召回严重偏移；
- 一改写 query 结果就完全不同。

**Phase to address:**
Phase 1（Query Normalization）

---

## Moderate Pitfalls

### Pitfall 9: 过早引入重工具链（浏览器渲染/深爬）作为默认路径
**What goes wrong:** 延迟与失败率上升，维护复杂度增加。  
**Prevention:** 默认轻路径，重工具仅在触发条件满足时兜底。  
**Phase to address:** Phase 4（Fallback Strategy）

### Pitfall 10: 输出模板不固定，导致易用性和稳定性评分波动
**What goes wrong:** 同题不同结构，评审难快速判断质量。  
**Prevention:** 固定输出骨架（结论/关键点/来源/时间版本/不确定点）。  
**Phase to address:** Phase 2（Output Contract）

## Minor Pitfalls

### Pitfall 11: 只优化平均值，不看尾部指标（P95/P99）
**What goes wrong:** 平均时间好看，但偶发超时拖低总分。  
**Prevention:** 以 P95 时延与失败率作为发布门槛。  
**Phase to address:** Phase 4（SLO Gate）

### Pitfall 12: 错误处理不区分“无结果”与“检索失败”
**What goes wrong:** 用户看到空洞答案或误判为事实不存在。  
**Prevention:** 明确错误类型并输出“证据不足/检索失败”状态。  
**Phase to address:** Phase 2（Failure Semantics）

## Phase-Specific Warnings

| Phase Topic | Likely Pitfall | Mitigation |
|-------------|---------------|------------|
| Phase 1: 题型路由与评测基线 | 单一路由 + 无重复运行评测 | 建立 10×5 稳定性基线，按题型分桶 |
| Phase 2: 证据标准化与输出契约 | 版本/辖区/文献元数据缺失 | 强制 evidence schema + canonical ID |
| Phase 3: 压缩与生成 | 盲目堆上下文导致 token/延迟失控 | Top-K 片段预算 + 逐事实引用 |
| Phase 4: 稳定性工程 | 外部源波动引发结果漂移 | 超时、重试、降级链、源健康监控 |
| Phase 5: 冲刺优化 | benchmark overfitting | 盲测集与消融实验，禁止题目特化硬编码 |

## Sources

### Internal project context
- `D:\study\WASC\.planning\PROJECT.md`
- `D:\study\WASC\比赛.txt`
- `D:\study\WASC\chatgpt\WASC_4月挑战赛参赛方案讨论稿.md`
- `D:\study\WASC\chatgpt\WASC_信源路由与基线策略.md`
- `D:\study\WASC\gemini\WASC搜索挑战赛落地方案.md`
- `D:\study\WASC\grok\需求.md`

### External references
- Federal Register corrections guidance: https://www.archives.gov/federal-register/write/ddh/correct (MEDIUM)
- GovInfo Federal Register issue archive example: https://www.govinfo.gov/content/pkg/FR-2026-02-11/pdf/FR-2026-02-11.pdf (MEDIUM)
- Retrieval Improvements Do Not Guarantee Better Answers (AI policy QA): https://arxiv.org/abs/2603.24580 (MEDIUM)
- Compound Deception in Peer Review (fabricated citations): https://arxiv.org/abs/2602.05930 (LOW-MEDIUM)
- citecheck (bibliographic verification): https://arxiv.org/abs/2603.17339 (LOW-MEDIUM)
- Preprint vs peer-reviewed differences (health, 2026): https://link.springer.com/article/10.1186/s41073-026-00189-z (MEDIUM)
- EverMemBench-S (RAG eval pitfalls): https://arxiv.org/abs/2601.20276 (LOW-MEDIUM)
- CRAG benchmark: https://papers.neurips.cc/paper_files/paper/2024/file/1435d2d0fca85a84d83ddcb754f58c29-Paper-Datasets_and_Benchmarks_Track.pdf (MEDIUM)
- RGB benchmark: https://arxiv.org/abs/2309.01431 (MEDIUM)
- FRAMES benchmark: https://arxiv.org/abs/2409.12941 (MEDIUM)
- SERP Sensor (ranking volatility signal): https://serpsensor.com/ (LOW-MEDIUM)

---
*Pitfalls research for WASC competition search skill (pitfalls dimension)*
*Researched: 2026-04-07*
