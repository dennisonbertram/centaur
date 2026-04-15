# Nightly Scorecard Format

Keep the nightly `ai-v2` post lean but informative.

## Required Fields

- Tasks reviewed
- Below-bar rate (percentage)
- Mean composite score (0-100)
- Top failure modes (up to 3, with counts)
- Selected fixes (fix type + title)
- PRs opened (with links)
- PRs merged (from recent deploy notifier runs)
- PRs deployed (from recent deploy notifier runs)
- Source threads notified

## Preferred Style

- One short heading line
- One compact summary line with the composite score and below-bar rate
- One flat bullet list for failure modes and fixes
- PR links inline
- No deep nesting
- No giant backlog dump
- No raw JSON in the Slack post

## Example

```
Self Improve Nightly

Reviewed 12 tasks. Mean score: 71/100. Below-bar rate: 25%.

- Top failure modes: verification_miss x3, intent_miss x2, research_miss x1
- Selected fixes:
- `workflow_fix` Add lint check before delivery in deploy workflows
- `prompt_tweak` Strengthen research-before-action guidance in eng persona
- PRs opened:
- [#42](https://github.com/.../42) Add lint check before delivery
- [#43](https://github.com/.../43) Strengthen research guidance
- PRs merged: 1
- PRs deployed: 1
- Source threads notified: 2
```
