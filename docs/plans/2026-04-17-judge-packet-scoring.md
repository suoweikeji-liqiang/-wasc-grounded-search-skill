# Judge Packet Scoring Implementation Plan

> **For Claude:** REQUIRED SUB-SKILL: Use superpowers:executing-plans to implement this plan task-by-task.

**Goal:** Export per-case answer/evidence packets that can be judged by Codex subagents with minimal context after a benchmark round.

**Architecture:** Add a small benchmark-side packet exporter that reads the existing case manifest, calls `/retrieve` and `/answer`, captures the response materials plus runtime summary, and writes one JSON packet per case plus one round index. Keep judging out of the repo runtime and do scoring later in the Codex session with `fork_context=false`.

**Tech Stack:** Python 3.12, FastAPI `TestClient`, existing benchmark models, pytest.

---

### Task 1: Lock the packet shape with failing tests

**Files:**
- Create: `tests/test_judge_packet_export.py`
- Reference: `skill/api/entry.py`
- Create later: `skill/benchmark/judge_packets.py`
- Create later: `scripts/export_judge_packets.py`

**Step 1: Write the failing packet-content test**

Add a test that proves a packet contains:

- `case_id`
- `query`
- `retrieve`
- `answer`
- `runtime`

and that `retrieve.canonical_evidence`, `answer.key_points`, and `answer.sources` survive serialization.

**Step 2: Run test to verify it fails**

Run:
`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q tests/test_judge_packet_export.py --import-mode=importlib`

Expected: FAIL because the exporter module does not exist yet.

**Step 3: Write the failing CLI test**

Add a test proving the exporter CLI:

- accepts a benchmark manifest path
- writes one packet per case
- writes an index JSON file

**Step 4: Run test to verify it fails**

Run:
`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q tests/test_judge_packet_export.py -k cli --import-mode=importlib`

Expected: FAIL because the CLI does not exist yet.

---

### Task 2: Add the packet exporter

**Files:**
- Create: `skill/benchmark/judge_packets.py`
- Create: `scripts/export_judge_packets.py`
- Test: `tests/test_judge_packet_export.py`

**Step 1: Implement packet building**

Create helpers that:

- load benchmark cases
- call `/retrieve`
- call `/answer`
- read `app.state.last_runtime_trace`
- build a minimal JSON-serializable packet

**Step 2: Implement round export**

Write:

- one packet file per case under an output directory
- one round index file listing all packet paths

**Step 3: Run tests**

Run:
`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q tests/test_judge_packet_export.py --import-mode=importlib`

Expected: PASS

---

### Task 3: Re-verify no public contract regression

**Files:**
- Test: `tests/test_api_runtime_benchmark.py`
- Test: `tests/test_benchmark_reports.py`
- Test: `tests/test_answer_contracts.py`

**Step 1: Run targeted regressions**

Run:
`PYTEST_DISABLE_PLUGIN_AUTOLOAD=1 python -m pytest -q tests/test_judge_packet_export.py tests/test_api_runtime_benchmark.py tests/test_benchmark_reports.py tests/test_answer_contracts.py --import-mode=importlib`

Expected: PASS

---

### Task 4: Generate one sample packet round

**Files:**
- Reference: `scripts/export_judge_packets.py`
- Output: `benchmark-results/<new-dir>/judge-packets/`

**Step 1: Run one local round**

Run the exporter against a small manifest or smoke set.

**Step 2: Inspect packet shape**

Confirm each packet contains only answer/evidence/runtime materials and no extra repo context.

**Step 3: Stop before auto-judging**

Do not implement in-repo judge scoring. The next step happens in the Codex session by spawning scoring agents with `fork_context=false`.
