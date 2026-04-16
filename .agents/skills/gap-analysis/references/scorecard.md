# Nightly Scorecard Format

Keep the nightly `ai-v2` post lean but informative.

## Required Fields

- Tasks reviewed
- Below-bar rate (percentage)
- Mean composite score (0-100)
- Top failure modes (up to 3, with counts)
- Selected fixes (fix type + title + human "why" narrative)
- PRs opened (with Slack-format links + human "why" narrative)
- PRs merged (from recent deploy notifier runs)
- PRs deployed (from recent deploy notifier runs)
- Source threads notified

## Preferred Style

- Bold section headers via Slack mrkdwn (`*Gap Analysis*`, `*Learning Synthesis*`, `*Execution*`)
- One compact summary line with the composite score and below-bar rate
- Two-space indent for bullets under a label (Slack renders this as a sub-list)
- Under each selected fix and each opened PR, include a `_Why:_` line — plain-English prose that names the users who surfaced the issue and what they were trying to do. This is the most valuable part of the post for human readers.
- PR links must use Slack link syntax `<url|#N>`, not GitHub-style `[#N](url)` (which Slack renders as literal text)
- No deep nesting beyond two levels
- No giant backlog dump
- No raw JSON in the Slack post

## Example

```
*Self Improve Nightly*

Reviewed 12 tasks. Mean score: 71/100. Below-bar rate: 25%.

*Gap Analysis*
- Top failure modes: verification_miss x3, intent_miss x2, research_miss x1
- Selected fixes:
  - `workflow_fix` Add lint check before delivery in deploy workflows
    - _Why:_ Josie shipped a pulumi change on Tuesday that failed CI because ruff wasn't run; Matt hit the same thing Thursday. The deploy workflow needs an explicit lint step so code changes can't skip verification even if the agent forgets.
  - `prompt_tweak` Strengthen research-before-action guidance in eng persona
    - _Why:_ Three of eight reviewed tasks (Arjun x2, Asher x1) showed the agent diving into edits without reading related files first. Tightening the eng-persona research reminder should curb this pattern.

*Execution*
- PRs opened:
  - <https://github.com/.../42|#42> Add lint check before delivery
    - _Why:_ Josie shipped a pulumi change on Tuesday that failed CI because ruff wasn't run; Matt hit the same thing Thursday. The deploy workflow needs an explicit lint step so code changes can't skip verification even if the agent forgets.
  - <https://github.com/.../43|#43> Strengthen research guidance
    - _Why:_ Three of eight reviewed tasks showed the agent diving into edits without reading related files first.
- PRs merged in last 24h: 1
- PRs deployed in last 24h: 1
- Source threads notified in last 24h: 2
```

The `_Why:_` narratives may reference user first names, what they asked for, and how the gap surfaced. They are only posted to the internal `ai-v2` channel. They are stripped from the fix packet before the implementing agent sees it, and must never appear in PR titles, bodies, or commits.
