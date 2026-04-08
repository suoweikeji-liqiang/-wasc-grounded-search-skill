# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Repository status

- This repository is currently a planning workspace for the WASC April search challenge, not an implemented application.
- There is no runnable codebase yet: no `package.json`, `pyproject.toml`, `requirements.txt`, `Makefile`, CI config, or test suite is present.
- Most current work is comparing strategy documents and converging on a submission architecture.

## Key source documents

- `比赛.txt` is the source of truth for contest constraints: required deliverables, scoring rubric, runtime environment (`Ubuntu 24.04`, `4 vCPU`, `16 GB RAM`), and the required model (`MiniMax-M2.7`). It also states the expected submission layout: `README.md`, `skill/SKILL.md`, `scripts/`, `SETUP.md`, `tests/`, `LICENSE`.
- `claude/需求.md` is the most end-to-end pipeline proposal: intent classification -> query expansion -> async multi-source search -> BM25/RRF ranking -> optional Provence pruning -> structured cited output.
- `chatgpt/WASC_4月挑战赛参赛方案讨论稿.md` and `chatgpt/WASC_信源路由与基线策略.md` focus on benchmark-driven design principles: route by query type, prefer lightweight retrieval paths, compress before summarizing, and optimize for the scoring axes rather than a generic search product.
- `gemini/WASC搜索挑战赛落地方案.md` proposes a leaner Python-oriented pipeline: intent routing -> async fetch -> local BM25 denoising -> grounded generation.
- `grok/需求.md` and `grok/需求2.md` explore a more MCP-heavy architecture with external search MCP servers, reranking/caching, and TeaRAG/TERAG/PPR-inspired compression ideas.

## Big-picture architecture in the docs

Across the proposal documents, the shared product idea is a low-cost, high-precision search skill for WASC. The repeated architecture pattern is:

1. Classify the incoming query (`policy`, `industry`, `academic`, or mixed).
2. Route the query to different search sources based on that intent.
3. Run retrieval in parallel with hard timeouts and fallbacks.
4. Deduplicate, rerank, and compress results locally before the model sees them.
5. Send only a small grounded context to `MiniMax-M2.7`.
6. Return structured output with source links, key points, and uncertainty markers.

Important framing: the documents optimize for the competition rubric in `比赛.txt` — latency, token cost, coverage, accuracy, runnability, stability, and usability.

## Commands

There are currently no repository-defined build, lint, or test commands.

Useful commands while the repo remains document-only:

- `git status --short` — inspect pending doc changes.
- `rg -n "MiniMax|BM25|RRF|Provence|TeaRAG|TERAG|路由|信源" .` — compare core techniques across proposal documents.
- `rg -n "README|SKILL.md|SETUP|tests|LICENSE" 比赛.txt` — re-check the required submission structure from the contest brief.

## Working guidance for future Claude instances

- Treat this repository as a planning archive first. Do not assume any one proposal is already the chosen implementation.
- If asked to start implementation, first decide which proposal to operationalize and whether the runnable project should live at the repo root or alongside the planning docs.
- When proposal documents disagree, trust `比赛.txt` for environment and submission requirements.
- Most proposals assume a Python-based skill/MCP implementation, but that implementation has not been scaffolded yet.
- Avoid inventing build/test instructions until real project files are added.

<!-- GSD:project-start source:PROJECT.md -->
## Project

**WASC High-Precision Search Skill**

This project is a WASC competition entry: a search Skill focused on low-cost, high-precision retrieval across policy/regulation, industry information, and academic literature queries. It is designed to produce structured, source-backed answers that score well on the WASC rubric, with an emphasis on accuracy, completeness, stability, and practical usability under the contest runtime constraints.

**Core Value:** For any benchmark query, the Skill returns a trustworthy, structured answer with clear source links and minimal unsupported claims.

### Constraints

- **Runtime**: Must fit the WASC evaluation environment (`Ubuntu 24.04`, `4 vCPU`, `16 GB RAM`) — required by contest rules.
- **Model**: Must target `MiniMax-M2.7` as the unified model in evaluation — required by contest rules.
- **Architecture**: No Playwright/browser automation in the core design — explicit user constraint.
- **Scope**: Competition-first optimization — tradeoffs should favor benchmark score, not broad product flexibility.
- **Quality bar**: Must work across policy, industry, and academic queries in one system — explicit product scope.
<!-- GSD:project-end -->

<!-- GSD:stack-start source:research/STACK.md -->
## Technology Stack

## Recommended Stack
### Core Technologies
| Technology | Version | Purpose | Why Recommended | Confidence |
|------------|---------|---------|-----------------|------------|
| Python | 3.12.x | 主运行时 | Ubuntu 24.04 竞赛环境友好；生态最全（检索/抽取/排序/评测） | HIGH |
| FastAPI | 0.135.2 | Skill API 暴露 | 轻量、性能够用、与 Pydantic v2 配合好，利于结构化输出和稳定性 | HIGH |
| Uvicorn | 0.44.0 | ASGI 服务 | FastAPI 标配，部署简单，竞赛环境启动成本低 | HIGH |
| mcp (Python SDK) | 1.27.0 | MCP Skill 协议实现 | 直接对齐 MCP-based Skill 形态，提交复用价值高 | HIGH |
| MiniMax-M2.7 (single-call synthesis) | 赛事统一模型 | 最终综合生成 | 赛事硬约束；前置本地压缩后只做 1 次合成最省 token | HIGH |
### Supporting Libraries
| Library | Version | Purpose | When to Use | Confidence |
|---------|---------|---------|-------------|------------|
| httpx | 0.28.1 | 异步并发抓取/API 请求 | 多源并发检索主干（超时、重试、连接池） | HIGH |
| pydantic | 2.12.5 | 输入/输出 schema 校验 | 强制结构化输出（结论/要点/来源/不确定项） | HIGH |
| trafilatura | 2.0.0 | 网页正文抽取与清洗 | 需要从通用网页抽正文时 | HIGH |
| rank-bm25 | 0.2.2 | 轻量初筛 rerank | 预算敏感、CPU-only、需要可解释 Top-N 时 | MEDIUM |
| RapidFuzz | 3.14.5 | 去重/标题归一化 | URL 不同但内容近似的候选去重 | HIGH |
| tenacity | 9.1.4 | 重试与退避 | 外部源超时/429 时提升稳定性分 | HIGH |
| orjson | 3.11.7 | 高速 JSON 序列化 | 高并发或日志量大时降延迟 | HIGH |
| semanticscholar | 0.12.0 | 学术元数据检索 | 学术题主路由（论文题录/摘要/引用） | HIGH |
| arxiv | 2.4.1 | arXiv 检索补充 | 学术题 fallback 或补充 | HIGH |
| ddgs | 9.11.3 | 通用 web 搜索入口 | 行业信息与政策长尾补充入口 | MEDIUM-HIGH |
### Development Tools
| Tool | Purpose | Notes |
|------|---------|-------|
| pytest | 回归与稳定性压测 | 按比赛 10 题 × 重复运行机制做自动回归 |
| locust / 自定义 asyncio bench | 延迟与稳定性基准 | 重点观察 P95 响应、失败率、token 波动 |
| Docker | 复现实验环境 | 固定 Ubuntu 24.04 + 依赖版本，避免评测漂移 |
## Installation (Python)
# Core
# Retrieval + processing
# Domain sources
## Alternatives Considered
| Recommended | Alternative | When to Use Alternative |
|-------------|-------------|-------------------------|
| ddgs + 规则路由 | Serper/Tavily/Bright Data | 你有稳定预算且需要更强商业索引一致性时 |
| rank-bm25 | FlashRank (0.2.10) | 你确认其模型与任务匹配且可复现收益时（但更新较旧，不建议默认主干） |
| trafilatura | 浏览器渲染抓取 | 仅在极少数 JS 重页面且高价值来源必须读取时（非默认） |
| 单机轻缓存（SQLite/本地） | 向量数据库（Milvus/OpenSearch） | 数据规模长期增长到“持续知识库”场景时，竞赛版不优先 |
## What NOT to Use
| Avoid | Why | Use Instead |
|-------|-----|-------------|
| Playwright/Selenium 作为主路径 | 与“低成本/高稳定/快响应”目标冲突；你已明确排除 | API/HTML 抽取主路径 + 规则化 fallback |
| 浏览器依赖的 web-search MCP 作为默认 | 资源抖动大、安装复杂、50 次稳定性风险高 | httpx + ddgs + trafilatura |
| “全量网页直接喂 LLM” | token 爆炸、幻觉与延迟上升 | BM25/规则筛选后 Top-K 片段再合成 |
| duckduckgo-search（旧包） | 已迁移到 ddgs，继续用旧包有维护风险 | ddgs |
| 过重多代理深度编排 | 在 4vCPU/16GB 下易超时且调优成本高 | 单路由器 + 单次合成调用 |
## Stack Patterns by Variant
- 用“站点约束 + 官方域名优先 + 时间版本字段校验”
- 因为政策题准确性核心是“权威原文 + 版本时效”
- semanticscholar 主路由，arxiv fallback
- 因为结构化元信息比通用搜索更稳、更省 token
- ddgs 多源拉取 + 可信度分层 + 去重
- 因为行业题没有单一真源，关键在多源整合且分层引用
## Version Compatibility
| Package A | Compatible With | Notes |
|-----------|-----------------|-------|
| fastapi 0.135.2 | pydantic 2.12.5 | 当前主流组合，适合 schema-first 输出 |
| fastapi 0.135.2 | uvicorn 0.44.0 | 标准 ASGI 组合 |
| httpx 0.28.1 | Python 3.12 | 并发检索稳定组合 |
| ddgs 9.11.3 | 替代 duckduckgo-search 8.1.1 | 新项目直接用 ddgs，避免旧包迁移成本 |
## Prescriptive Recommendation (一句话)
- [mcp (PyPI)](https://pypi.org/project/mcp/)
- [FastAPI (PyPI)](https://pypi.org/project/fastapi/)
- [uvicorn (PyPI)](https://pypi.org/project/uvicorn/)
- [httpx (PyPI)](https://pypi.org/project/httpx/)
- [pydantic (PyPI)](https://pypi.org/project/pydantic/)
- [trafilatura (PyPI)](https://pypi.org/project/trafilatura/)
- [rank-bm25 (PyPI)](https://pypi.org/project/rank-bm25/)
- [FlashRank (PyPI)](https://pypi.org/project/FlashRank/)
- [RapidFuzz (PyPI)](https://pypi.org/project/RapidFuzz/)
- [tenacity (PyPI)](https://pypi.org/project/tenacity/)
- [orjson (PyPI)](https://pypi.org/project/orjson/)
- [semanticscholar (PyPI)](https://pypi.org/project/semanticscholar/)
- [arxiv (PyPI)](https://pypi.org/project/arxiv/)
- [duckduckgo-search (PyPI)](https://pypi.org/project/duckduckgo-search/)
- [ddgs (PyPI)](https://pypi.org/project/ddgs/)
- [scikit-learn (PyPI)](https://pypi.org/project/scikit-learn/)
- [sentence-transformers (PyPI)](https://pypi.org/project/sentence-transformers/)
<!-- GSD:stack-end -->

<!-- GSD:conventions-start source:CONVENTIONS.md -->
## Conventions

Conventions not yet established. Will populate as patterns emerge during development.
<!-- GSD:conventions-end -->

<!-- GSD:architecture-start source:ARCHITECTURE.md -->
## Architecture

Architecture not yet mapped. Follow existing patterns found in the codebase.
<!-- GSD:architecture-end -->

<!-- GSD:skills-start source:skills/ -->
## Project Skills

No project skills found. Add skills to any of: `.claude/skills/`, `.agents/skills/`, `.cursor/skills/`, or `.github/skills/` with a `SKILL.md` index file.
<!-- GSD:skills-end -->

<!-- GSD:workflow-start source:GSD defaults -->
## GSD Workflow Enforcement

Before using Edit, Write, or other file-changing tools, start work through a GSD command so planning artifacts and execution context stay in sync.

Use these entry points:
- `/gsd-quick` for small fixes, doc updates, and ad-hoc tasks
- `/gsd-debug` for investigation and bug fixing
- `/gsd-execute-phase` for planned phase work

Do not make direct repo edits outside a GSD workflow unless the user explicitly asks to bypass it.
<!-- GSD:workflow-end -->

<!-- GSD:profile-start -->
## Developer Profile

> Profile not yet configured. Run `/gsd-profile-user` to generate your developer profile.
> This section is managed by `generate-claude-profile` -- do not edit manually.
<!-- GSD:profile-end -->
