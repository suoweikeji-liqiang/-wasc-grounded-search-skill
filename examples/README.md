# Examples And Reproduction

This directory provides lightweight test-style examples for review.

## 1. Route Example

Input:

```json
{"query":"evidence normalization benchmark paper"}
```

Command:

```powershell
python .\scripts\route_query.py "evidence normalization benchmark paper"
```

Expected output characteristics:

- `route_label` is present
- `primary_route` is present
- `browser_automation` is `disabled`

## 2. Retrieve Example

Input:

```json
{"query":"NIS2 significant incident early warning deadline official text"}
```

Command:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/retrieve -ContentType 'application/json' -Body '{"query":"NIS2 significant incident early warning deadline official text"}'
```

Expected output characteristics:

- `status`
- `canonical_evidence`
- `results`
- `gaps`

## 3. Answer Example

Input:

```json
{"query":"EU Battery Regulation due diligence obligations SME exemption official text"}
```

Command:

```powershell
Invoke-RestMethod -Method Post -Uri http://127.0.0.1:8000/answer -ContentType 'application/json' -Body '{"query":"EU Battery Regulation due diligence obligations SME exemption official text"}'
```

Expected output characteristics:

- `answer_status`
- `retrieval_status`
- `conclusion`
- `key_points`
- `sources`
- `uncertainty_notes`

## 4. Mixed Query Example

Input:

```json
{"query":"FTC junk fees rule and ticketing platform checkout flow update"}
```

Expected behavior:

- if both sides are supported, the answer should synthesize both
- if only one side is supported, the answer should explicitly state which half is still missing
- the missing-side description should reuse the query-specific fragment rather than generic placeholder text

## 5. Reviewer Notes

The Skill is optimized for:

- groundedness
- structured output
- bounded retrieval
- useful partial answers when full evidence is unavailable

The public demo / video link should be supplied separately at submission time.
