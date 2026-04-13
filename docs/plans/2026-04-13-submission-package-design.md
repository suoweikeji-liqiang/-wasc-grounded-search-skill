# Submission Package Design

## Goal

Create a competition-ready repository submission package for the WASC High-Precision Search Skill.

## Scope

Files to add:

- `README.md`
- `SKILL.md`
- `SETUP.md`
- `LICENSE`

Supporting design record:

- `docs/plans/2026-04-13-submission-package-design.md`

## Decisions

### Packaging Approach

Chosen approach: full submission package rather than minimum-compliance placeholders.

Reason:

- the codebase already has verified benchmark evidence
- the missing gap is reviewer-facing documentation, not product capability

### README Strategy

The README should act as the main review entrypoint and include:

- problem statement
- verified benchmark and test evidence
- quick start commands
- API and CLI entrypoints
- runtime controls
- known limitations

### SKILL Strategy

`SKILL.md` should stay short and operational:

- what the Skill does
- accepted input
- output contract
- processing flow
- explicit non-goals

### Setup Strategy

`SETUP.md` should prioritize reproducibility:

- environment requirements
- installation
- env vars
- startup commands
- benchmark/test commands
- troubleshooting

### License Strategy

Use standard MIT for clear submission-time licensing.

## Accuracy Rules

- only include benchmark numbers already verified in local artifacts
- only describe public interfaces that exist in code
- do not fabricate demo links or unsupported capabilities

## Approved Content Direction

- full package, not minimal placeholders
- competition-first tone
- no marketing fluff
- no claims beyond current `v1.0` evidence
