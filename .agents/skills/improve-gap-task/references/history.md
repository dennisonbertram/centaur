# Self-Improve Intervention Log

Append-only record of shipped interventions and failed attempts.

Before proposing a fix, check this log to avoid re-attempting fixes that already failed or are already in progress.

## PR Handoff Convention

Use PR labels plus a hidden PR-body metadata block as the only cross-system handoff.

Required labels:

- `self-improve`
- `fix-type:<type>`

Required metadata block shape:

```markdown
<!-- self_improve_metadata_v1:start -->
{"parent_run_id":"...","child_run_id":"...","fix_type":"workflow_fix","source_threads":[{"thread_key":"C123:1700.100","channel":"C123","thread_ts":"1700.100"}],"summary":"Short user-facing summary"}
<!-- self_improve_metadata_v1:end -->
```

Rules:

- Preserve the JSON exactly.
- Do not add a second tracking system.
- Keep the PR narrowly focused on the selected fix.

## Intervention Log

Each entry records one attempted fix and its outcome.

Format:

```
### YYYY-MM-DD: <fix title>
- fix_type: <type>
- pr: <pr_url or "not opened">
- outcome: <merged | closed | pending | abandoned>
- failure_mode_addressed: <the failure mode from gap analysis>
- impact_notes: <what changed after merge, if anything>
```

---

(No entries yet. The nightly loop will append entries here as fixes are shipped.)
