# Phase 3: Evidence Normalization & Budgeted Context - Discussion Log

> **Audit trail only.** Do not use as input to planning, research, or execution agents.
> Decisions are captured in CONTEXT.md - this log preserves the alternatives considered.

**Date:** 2026-04-12
**Phase:** 03-evidence-normalization-budgeted-context
**Areas discussed:** Evidence unit shape, Duplicate collapse policy, Policy metadata completeness, Academic canonicalization, Budgeted context packing

---

## Evidence unit shape

| Option | Description | Selected |
|--------|-------------|----------|
| Document + evidence slices | One canonical document record with retained quote/snippet slices under it. | X |
| Document only | Only document-level canonical records, no retained slice layer yet. | |
| Slice only | Each snippet/chunk is treated as the main evidence unit. | |

**User's choice:** Document + evidence slices
**Notes:** Also chose to keep both raw and normalized records internally, retain up to 2 slices per document, and optimize the normalized object for downstream traceability first.

---

## Duplicate collapse policy

| Option | Description | Selected |
|--------|-------------|----------|
| Policy URL-only / title-first / aggressive event merge | Simpler or more aggressive duplicate handling. | |
| Domain-specific conservative collapse | Policy uses document identity plus version/date-aware matching; academic uses DOI then arXiv ID then title/author/year; industry uses same-domain high-similarity near-duplicate collapse. | X |
| Aggressive semantic merge | Merge broad same-event or same-topic items even when not near-exact duplicates. | |

**User's choice:** Domain-specific conservative collapse
**Notes:** Complementary metadata from duplicates should be merged into the canonical record instead of discarded.

---

## Policy metadata completeness

| Option | Description | Selected |
|--------|-------------|----------|
| Strict rejection on missing metadata | Drop policy items whenever version, jurisdiction, or effective date is missing. | |
| Keep with explicit incompleteness markers | Preserve useful policy evidence but mark missing version/jurisdiction/effective date explicitly. | X |
| Keep silently | Keep incomplete policy evidence without explicit markers. | |

**User's choice:** Keep with explicit incompleteness markers
**Notes:** Minimum bar is authority plus at least one date field. `publication_date` and `effective_date` stay separate. Missing jurisdiction may be inferred or unknown, but never silently defaulted.

---

## Academic canonicalization

| Option | Description | Selected |
|--------|-------------|----------|
| Published-first canonicalization | Published record becomes canonical when matched; preprint stays as linked provenance. | X |
| Richest-metadata-first canonicalization | Whichever version has better metadata becomes canonical. | |
| Preprint-first canonicalization | Keep arXiv/preprint as canonical by default. | |

**User's choice:** Published-first canonicalization
**Notes:** Non-canonical versions should remain as linked variants. Evidence level should be explicit (`peer_reviewed`, `preprint`, `survey_or_review`, `metadata_only`). Heuristic canonical matches are allowed only with an explicit confidence marker.

---

## Budgeted context packing

| Option | Description | Selected |
|--------|-------------|----------|
| Hard token budget + top-K cap | Use a hard token budget with a top-K ceiling and prune by score when necessary. | X |
| Fixed K only | Keep a fixed number of items regardless of size. | |
| Token-only without cap | Only enforce token budget and let item count float. | |

**User's choice:** Hard token budget + top-K cap
**Notes:** Use one global budget with a small protected minimum share for the supplemental route in mixed queries. When over budget, prune low-scoring slices before dropping whole documents. Keep detailed budget state internal and expose only whether clipping occurred externally.

---

## the agent's Discretion

- Exact field names for canonical records, retained slices, linked variants, and clip indicators.
- Exact similarity thresholds for heuristic academic matching and industry near-duplicate collapse.
- Exact budget constants and slice scoring formula, as long as the chosen enforcement policy is preserved.

## Deferred Ideas

None - discussion stayed within phase scope.
