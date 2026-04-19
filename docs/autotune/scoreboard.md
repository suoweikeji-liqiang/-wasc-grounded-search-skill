# Autotune Scoreboard

This table tracks benchmark and judge movement for each preserved autotune round.

| Round | Hypothesis | Grounded Success | Judge Score | Benchmark Delta | Judge Delta | Decision |
| --- | --- | --- | --- | --- | --- | --- |
| baseline-001 | Establish baseline on 2026-04-15 generalization round 2 holdout | 0.380 | 0.406 | +0.000 | +0.000 | baseline |
| round-001 | Allow bounded same-route enrichment to rescue thin partial industry lookups into grounded fast paths | 0.220 | 0.429 | -0.160 | +0.023 | rejected |
| round-002 | Speculatively prewarm the policy allowlist fallback after a bounded registry head-start to reduce serial timeout chains on authoritative lookups | 0.440 | 0.267 | +0.060 | -0.139 | rejected |
| round-003 | Prefer policy records whose canonical titles match distinctive query terms before generic metadata tie-breaks so named acts outrank adjacent official texts in policy fast paths. | 0.480 | 0.331 | +0.100 | -0.075 | kept |
| round-004 | Promote narrow policy fast-path direct answers when the query explicitly asks for an effective date or definition and the retained official record already contains that exact metadata or wording. | 0.600 | 0.326 | +0.120 | -0.080 | kept |
| round-005 | For US policy queries and other direct-source-favored lookups, do not let a weaker registry hit outrank a stronger direct official source that is already available in the same retrieval wave. | 0.480 | - | -0.120 | - | rejected |
| round-006 | Prefer stronger direct official policy records over weaker registry/Federal Register hits, and preserve upstream relevance when equal-scored policy evidence is pruned. | 0.660 | 0.372 | +0.060 | -0.034 | kept |
| round-007 | Promote clause-rich official-source snippets into direct policy fast-path conclusions when retained official evidence already contains concrete deadline, obligation, or enforcement detail. | 0.520 | 0.442 | -0.140 | +0.036 | kept |
| round-008 | Prefer arXiv as the first academic metadata source when the query explicitly hints paper repositories or is a year-heavy paper lookup, so academic routes avoid semantic-scholar-first timeout chains without restoring the old parallel fan-out. | 0.520 | - | -0.140 | - | rejected |
| round-009 | Reserve bounded retry budget for high-priority academic query variants so one timed-out condensed variant does not consume the full metadata source budget before a follow-up scholarly variant can run. | 0.480 | - | -0.180 | - | rejected |
| round-010 | Prefer better direct official policy records and clause-rich official snippets so named policy lookups stay on stronger local fast paths. | 0.260 | - | -0.400 | - | rejected |
| round-011 | Forward richer EUR-Lex clause text into policy fast-path conclusions without changing retrieval ranking. | 0.240 | - | -0.420 | - | rejected |
| round-032 | Rebuild strong policy direct-source and policy fast-path wins, fix filing-vs-policy ambiguity, and add standards/CBAM official aliases without broadening retrieval fan-out. | 0.880 | - | +0.220 | - | candidate |
| round-033 | Short-circuit exact standards aliases and allow single-source standards exact-token lookups onto the industry fast path so FedCM, ETSI, and RFC6265bis queries stop timing out or degrading to partial answers. | 0.920 | - | +0.260 | - | candidate |
