# Step 2 regression note (2026-04-17)

Step: `§2 Step 2 - Industry live cascade total budget`

Status: negative validation result on fresh 40-case non-mixed rerun. No commit created.

## Manifest used

- Source fixture: `tests/fixtures/benchmark_generated_hidden_like_cases_2026-04-15_generalization_round2.json`
- Temporary non-mixed 40-case manifest:
  `benchmark-results/_tmp_gen3_nonmixed_cases_2026-04-17.json`

## Validation command

```powershell
python .\scripts\run_benchmark.py `
  --cases .\benchmark-results\_tmp_gen3_nonmixed_cases_2026-04-17.json `
  --runs 1 `
  --fresh-process `
  --output-dir .\benchmark-results\gen3-nonmixed-r2-post-step2
```

## Measured delta

Before: `benchmark-results/gen3-nonmixed-r1-fresh-2026-04-17/`

- overall `12/40`
- policy `5/10`
- academic `7/10`
- industry `0/10`
- hard `0/10`

After: `benchmark-results/gen3-nonmixed-r2-post-step2/`

- overall `8/40`
- policy `5/10`
- academic `3/10`
- industry `0/10`
- hard `0/10`

This violates the step guardrail:

- industry did not improve by at least `+1`
- academic dropped by more than `1`

## Cases that changed

- `gen3-academic-06`: `grounded_success -> insufficient_evidence`
- `gen3-academic-07`: `grounded_success -> insufficient_evidence`
- `gen3-academic-09`: `grounded_success -> insufficient_evidence`
- `gen3-academic-10`: `grounded_success -> insufficient_evidence`
- `gen3-hard-01`: `retrieval_failure -> insufficient_evidence`
- `gen3-industry-01`: `insufficient_evidence -> retrieval_failure`
- `gen3-industry-04`: `retrieval_failure -> insufficient_evidence`
- `gen3-industry-05`: `retrieval_failure -> insufficient_evidence`
- `gen3-industry-06`: `retrieval_failure -> insufficient_evidence`
- `gen3-industry-08`: `retrieval_failure -> insufficient_evidence`

## Likely implication

The new adapter-local budget did not raise `industry` grounded success, and it appears
to have shifted some cases from `retrieval_failure(timeout)` to `insufficient_evidence`
without producing additional grounded hits. Fresh-run variance also regressed unrelated
academic cases, so this step should not be carried forward without further diagnosis.
