# Codex execution plan — post hard-cap landing (2026-04-17)

Opus authored this plan. Codex executes step-by-step, one atomic commit per
step, validating with the gen3 non-mixed fresh slice, not smoke. Do not
deviate without explicit user approval. If a step's measured delta is not in
the expected direction, STOP and report before touching the next step.

---

## 0. Ground state (as of commit `e40bb9a`)

- **Truth benchmark:** `benchmark-results/gen3-nonmixed-r1-fresh-2026-04-17/`
  - baseline before any of today's work: `12 / 40` grounded_success,
    `28 / 40` timeout, judge proxy `39 / 39 / 40`
- **Per-bucket baseline:**
  - `academic: 7/10` (3 insufficient_evidence, all ~6s)
  - `policy:   5/10` (5 retrieval_failure at ~6s — local deadline hits)
  - `industry: 0/10` (8 retrieval_failure, 2 insufficient_evidence; 6 of them
    were hitting the `60 000 ms` harness subprocess hard kill)
  - `hard:     0/10` (mostly routed to industry; all short early failures)
- **Commit `e40bb9a` effect (just landed):**
  - `execute_answer_pipeline_with_trace` is now wrapped in `asyncio.wait_for`
    at `request_deadline_seconds + 1.5s` grace
  - the 6 industry cases that were hitting `60 000 ms` will now return
    `retrieval_failure/timeout` at `~11 500 ms`; their pass/fail verdict is
    UNCHANGED, but per-suite total time drops by ~4.8 min, and subsequent
    adapter-level fixes will no longer be masked by the outer 60s harness
    kill
- **Pre-existing uncommitted working-tree drift** (NOT mine; do not sweep it
  into any of your commits unless it is the specific thing you are fixing):
  - `skill/synthesis/orchestrate.py` has a substantial uncommitted block of
    coverage-frontier multi-route work (new `_COVERAGE_FRONTIER_VARIANT_PRIORITY`
    per-route tables, expanded `_choose_coverage_frontier_variant`, etc.)
  - several modified test files match that work
  - leave them alone for now

---

## 1. Decisions already locked in (do not re-litigate)

- Optimize to `gen3-nonmixed-r1-fresh-2026-04-17/` style broad fresh slices.
  Smoke gates (round36/37 etc.) are sanity checks, not objectives.
- Do NOT optimize for `mixed` bucket.
- Do NOT edit `skill/synthesis/orchestrate.py` answer-shaping code paths
  (prompt building, `_build_*_response`, phrasing). Adding/restructuring
  `execute_answer_pipeline_with_trace` itself for budget enforcement is
  allowed; touching `_compose_*` / conclusion / key_points / source
  formatting is not.
- Do NOT add query-string keyword bandaids. If a change only helps one
  benchmark case by matching a specific phrase, reject it.
- Every commit message must name the benchmark slice used to validate it
  and the bucket-level before/after numbers.

---

## 2. Step-by-step plan

### Step 2 — Industry live cascade total budget

**Hypothesis.** In `skill/retrieval/adapters/industry_ddgs.py::search_official_or_filings_live`
(starts around line 2169), the body runs these in sequence:

1. `_search_prioritized_sec_records` / `_search_fastest_sec_records`
   (each with its own ~4s per-request timeout, `sec_edgar.py:274/373/442`)
2. `_search_known_company_ir_page_candidates` (company IR home + page fetch,
   each ~2.5–4s)
3. `_official_search_queries` → `search_multi_engine` gather (web queries,
   multiple engines × multiple variant queries; each ~3s)
4. Final `_rank_payloads_to_hits`

The engine wraps the adapter with `asyncio.wait_for(adapter(query),
timeout=timeout_seconds)` (see `skill/retrieval/engine.py:660`), where
`timeout_seconds` for industry primary is the per-source value
(`_PRIMARY_INDUSTRY_PER_SOURCE_TIMEOUT_SECONDS = 8.0`, in
`skill/orchestrator/retrieval_plan.py:47`). That SHOULD cap it — but the
hard-cap data (see "Why industry-04..09 hit 60s" below) shows cancellation
is lossy.

**Why industry-04..09 hit 60s on master.** When `wait_for` cancels, the
adapter's `try: await asyncio.gather(...)  except asyncio.CancelledError:
await _cancel_search_tasks(...); raise` (line 2231, 2373, 1068) awaits the
in-flight tasks before re-raising. Those in-flight tasks do HTTP fetches
via httpx with their own per-request timeout, so in the worst case the
cancellation is gated on the slowest outstanding fetch completing/timing
out. With multiple stages layered this way, cancellation can chain through
many tens of seconds. Hard-cap in commit `e40bb9a` now catches it, but we
want the adapter to bail FAST at its own layer too, both to (a) free the
budget for the backup chain and (b) let `industry_web_discovery` /
`industry_news_rss` actually run.

**Fix.** Give `search_official_or_filings_live` a single internal hard
budget `_INDUSTRY_OFFICIAL_OR_FILINGS_LIVE_BUDGET_SECONDS = 6.0` (new
module-level constant near the other live constants). Record
`started_at = loop.time()` at entry. Before each sequential stage
(`_search_prioritized_sec_records` call, IR candidate call, and
`asyncio.gather(*official_query_tasks)` call), check remaining budget.

- If remaining budget ≤ 0, skip that stage and proceed to `_rank_payloads_to_hits`
  with whatever candidates are accumulated so far.
- For the final `asyncio.gather` of official query tasks, wrap it in
  `asyncio.wait_for(asyncio.gather(...), timeout=max(0.1, remaining))`. On
  `TimeoutError`, cancel with the existing `_cancel_search_tasks_detached`
  helper (non-blocking cancel; do NOT await it) and continue with the
  candidates already collected.
- Apply the same pattern to `search_live` (around line 2251) — same stages,
  same issue, share the same constant.

**Do NOT:**
- introduce a new `asyncio.TimeoutError`-based control-flow wrapper around
  the whole function (that would duplicate what the engine already does)
- change per-subrequest httpx timeouts (separate lever, out of scope here)
- change any `_rank_payloads_to_hits` behaviour

**Test coverage.** Add `tests/test_industry_live_cascade_budget.py` with at
least two tests:

1. Monkey-patch `_search_fastest_sec_records` to `await asyncio.sleep(10)`
   and verify that `search_official_or_filings_live` returns within `~6.5s`
   (budget + tolerance) and that later stages are skipped (assert by
   observing which mocks were invoked).
2. With all stages fast (return `[]`) and under a non-stressed event loop,
   verify the function still returns normally and `_rank_payloads_to_hits`
   was called.

Run `pytest tests/test_industry_live_cascade_budget.py
tests/test_industry_live_adapter.py tests/test_industry_source_split.py
tests/test_request_deadline_guard.py -q` before commit.

**Validation.** Re-run the fresh slice:

```
python -m skill.benchmark.cli run \
  --cases benchmark-results/gen3-nonmixed-r1-fresh-2026-04-17/... \
  --fresh-process \
  --output-dir benchmark-results/gen3-nonmixed-r2-post-step2/
```

(Replace the cases path with whatever generates the same 40-case slice —
check how the original gen3 run was produced. If the case manifest is not
reproducible, at minimum re-run the 10 industry cases + 10 hard cases as a
targeted subset.)

**Expected effect.** `industry` goes from `0/10` to `2–4/10`. Timeouts in
industry drop by the 6 cases that previously hit harness-kill. `hard`
bucket's industry-routed cases may also pick up 1–2.

**STOP and report if:** industry grounded_success does not increase by at
least 1, OR other buckets drop by more than 1. Those outcomes indicate the
budget is cutting a stage that was producing the hits — would need to
re-tune.

**Commit message template:**

```
industry: enforce total budget on official-or-filings live cascade

<one-paragraph reason tied to 60s harness kill evidence>

Before (gen3-nonmixed-r1-fresh-2026-04-17):
  industry 0/10 (8 retrieval_failure, 2 insufficient_evidence)
After  (gen3-nonmixed-r2-post-step2):
  industry X/10 (...)
  hard     Y/10 (...)
Overall: Z/40 grounded_success
```

---

### Step 3 — Policy early-deadline allowlist fallback

**Hypothesis.** Policy bucket has 5 cases that timeout at ~6s:
`gen3-policy-01/05/08/09/10`. The overall policy retrieval deadline is
`OVERALL_RETRIEVAL_DEADLINE_SECONDS = 6.0` (`skill/config/retrieval.py:11`).
First wave only fires `policy_official_registry`. If that source consumes
the full 6s and yields `timeout`, the fallback chain
`policy_official_web_allowlist_fallback` (see `SOURCE_BACKUP_CHAIN`) never
gets time to run.

**Fix.** Reserve fallback time for policy primary-only plans. Two possible
shapes — pick (a) unless testing reveals issues:

(a) In `skill/orchestrator/retrieval_plan.py`, introduce a
`_PRIMARY_POLICY_PRIMARY_PER_SOURCE_TIMEOUT_SECONDS = 3.5` constant and
apply it when `route_label == "policy"` and `primary_route == "policy"`
and `supplemental_route is None`. Keep `overall_deadline_seconds = 6.0`.
This way the primary source cannot consume more than 3.5s, leaving ≥2.5s
for the allowlist fallback.

(b) Alternative if (a) measures worse: bump overall to 7.5s for this case
only (plan-level change in the same file) — likely worse because it leaks
into request deadline pressure; try (a) first.

**Do NOT:**
- change `OVERALL_RETRIEVAL_DEADLINE_SECONDS` globally
- change the policy route's first-wave source set
- touch `skill/retrieval/live/clients/policy_us_agencies.py` in this step
  (its internal timeouts are a separate lever)

**Tests.** Add/extend a test that constructs a policy-only plan and
asserts `per_source_timeout_seconds <= 3.5` (not the default 3.0, and
not the 8.0 industry override). Reuse `tests/test_retrieval_plan.py`
patterns.

**Validation.** Same fresh slice rerun as step 2. Diff only the `policy`
bucket and the overall total.

**Expected effect.** Policy 5/10 → 7/10, overall +2 cases. If unchanged,
investigate whether `policy_us_agencies` live client has internal
synchronous work (DNS, redirects) that ignores per-source budget.

**STOP and report if:** policy bucket drops or primary policy source loses
cases that were previously succeeding.

---

### Step 4 — Hard bucket re-measurement

**Do not code anything for this step until steps 2 and 3 have landed.**
Most hard bucket cases route to industry or policy, so the real delta will
be driven by steps 2 and 3. After rerunning the fresh slice, check hard
bucket:

- If `hard ≥ 3/10`: declare success, close step 4.
- If `hard < 3/10`: separately look at the 2–3 hard industry cases that
  are still failing. Likely candidates are high-CJK queries or RFC-style
  exact-token queries; these may need route-specific variant hints. DO
  NOT add keyword bandaids. If there is no generalizable fix, leave them.

---

### Step 5 — Academic `insufficient_evidence` reduction (optional)

Only touch this if steps 2–4 have shipped and measured improvements
stuck. Three cases: `gen3-academic-03/07/08` return
`insufficient_evidence` not `timeout`. They are "survey-style 2025/2026
arXiv" queries where `academic_semantic_scholar` returns results but
their relevance score falls below the threshold and the fallback chain
gives up.

Likely levers:
- relax the relevance gate in `skill/retrieval/adapters/academic_semantic_scholar.py`
  for recent-year list queries (`traits.has_trend_intent == True`)
- add `arxiv` as a retained fallback (currently set to None in
  `SOURCE_BACKUP_CHAIN`) with a tight budget

Out of Opus's scope for now. Open a fresh plan entry when we get here.

---

## 3. Mixed-leak hygiene (tracking only — not a scoring item)

After step 2 lands, confirm `gen3-policy-10` and `gen3-industry-10` still
emit `route_label == "mixed"` in their runtime trace. If yes, log it as a
known debt item. DO NOT fix during any of the scoring steps. It is worth
at most 0–2 cases and touching the route labeler risks regressions across
the whole suite.

If you must, the fix lives in `skill/orchestrator/intent.py` — search
for where `route_label = "mixed"` is set and ensure it is gated on the
query actually being multi-domain rather than ambiguously keyworded.

---

## 4. Workflow rules for codex

1. **One fix per commit.** Each commit shows before/after bucket numbers
   from the same gen3 fresh slice. Anything else → separate commit.
2. **Do not sweep the uncommitted drift into your commits.** The working
   tree already has unstaged changes to multiple files from previous
   sessions. When you commit your own fix, use explicit `git add <path>`
   for the exact files you touched. Run `git status --short` and confirm
   only your intended paths are staged. If you see files you did not
   modify in your staged list, unstage them before committing.
3. **No `--amend`, no `--no-verify`.** Add a new commit if you need to
   correct something.
4. **Do not touch `skill/synthesis/orchestrate.py`.** The one exception
   is if you need to adjust the hard-cap grace or fallback text added by
   commit `e40bb9a`, and even then only with explicit evidence.
5. **Always run** `pytest tests/test_request_deadline_guard.py` before
   commit. The guard is the reason the benchmark is now measurable; if
   you break it, you are back to 60s harness kills.
6. **Benchmark cadence:**
   - After step 2 → one fresh rerun
   - After step 3 → one fresh rerun
   - Do NOT rerun more than necessary; each fresh 40-case run is
     expensive and the variance between runs is low enough that a single
     run per step is fine.
7. **If a step's measured delta is negative or zero**, revert the commit
   (`git revert <sha>`), write what you saw in a short note under
   `.planning/forensics/`, and ping the user before proceeding.

---

## 5. What Opus explicitly DID NOT touch

- Any live retrieval adapter logic
- Any policy or academic client internals
- Query traits / intent classification
- Coverage-frontier logic (there is uncommitted work there from a prior
  session — leave it alone unless the user asks)
- Answer synthesis phrasing

If codex thinks one of these needs a touch for step 2 or 3 specifically,
ping the user first. The hard-cap commit was deliberately the *only*
behavior change today; everything else is codex's to drive with the
guardrails above.
