# SKILL: WASC High-Precision Search Skill

## Purpose

This Skill solves low-cost, high-precision search tasks by:

1. routing a query to the right evidence family
2. retrieving bounded source-backed evidence
3. returning a structured grounded answer with citations

## Input

```json
{"query":"user query text"}
```

## Public Output

Main answer surface: `POST /answer`

Returned fields:

- `answer_status`
- `retrieval_status`
- `conclusion`
- `key_points`
- `sources`
- `uncertainty_notes`
- `gaps`

Answer states:

- `grounded_success`
- `insufficient_evidence`
- `retrieval_failure`

## Main Strengths

- grounded answers rather than unsupported synthesis
- support for policy, industry, academic, and mixed queries
- explicit partial-answer behavior when evidence is incomplete
- bounded live retrieval behavior for self-serve use

## Main Files

- `skill/api/entry.py`
- `skill/api/schema.py`
- `skill/retrieval/*`
- `skill/evidence/*`
- `skill/synthesis/*`

## Setup And Examples

- setup: [SETUP.md](./SETUP.md)
- submission mail template: [submit-template.txt](./submit-template.txt)
- reproducible examples: [examples/README.md](./examples/README.md)
