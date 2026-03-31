---
name: talent-placement-updates
description: Tracks who Paradigm introduced or helped hire into portfolio companies and verifies where they are now. Use when asked for talent placement updates, portfolio-company hire tracking, current-employer validation, or network movement reports.
---

# Talent Placement Updates

Builds a conservative talent-placement update from `paradigmdb`, then validates current-employer status with fresher sources and marks ambiguous cases `Uncertain`.

## Core Rule

Default to `Uncertain`.

Do not mark someone `Still there` or `Left` unless there is strong, post-hire evidence.

## What This Skill Produces

- A seeded roster of portfolio-company hires from `paradigmdb`
- A validated status for each person: `Still there`, `Left`, or `Uncertain`
- A summary with counts
- A CSV or table with evidence notes for every row

## Workflow

### 1. Build the Seed Roster From `paradigmdb`

Use `TalentSupport` as the initial source of truth for Paradigm-assisted placements.

Start with:

- `TalentSupport` rows where `type = HIRE`
- `Person` for candidate metadata
- `Organization` for hired-company metadata

Capture at minimum:

- hire date
- candidate name
- hired company
- hired role
- candidate LinkedIn URL
- any linked internal person or org ids

If the same person has multiple HIRE rows, keep all of them in the working dataset but identify the latest hire separately.

If a HIRE row has no linked `candidatePersonId`, keep it and mark it `Unresolved` or `Uncertain` unless a later external lookup identifies the person confidently.

### 2. Treat Internal CRM Data As Seed Data, Not Final Truth

`Person.primaryOrganizationId`, `Person.title`, Affinity organization ids, or other internal CRM fields are useful hints, but they are not definitive current-employer proof.

Use them to:

- prioritize who to investigate
- formulate search queries
- identify likely mismatches

Do not use them alone to mark `Still there` or `Left`.

### 3. Validate With Fresher Sources

Use fresher sources in this order when available:

1. Public LinkedIn profile text
2. Recent authored or shared LinkedIn activity that clearly ties the person to a company or role
3. Slack references, if they are recent and clearly identify the person and company
4. Affinity or other CRM systems, only as supporting evidence

Prefer direct statements about the person over inference from likes, follows, or stale profile blocks.

For LinkedIn, prefer `read_web_page` against the public profile URL over ad hoc scraping. Raw `curl` or direct HTML fetches are often rate-limited or blocked and should not be treated as reliable absence of evidence.

## Evidence Thresholds

### Strong Enough To Mark `Still there`

Examples:

- The profile `About` explicitly states a current role at the portco
- A recent authored or shared post clearly says they joined, work at, or are hiring for the portco
- A strong profile-specific CTA or intro banner clearly ties the person to the portco now

### Strong Enough To Mark `Left`

Examples:

- The profile `About` explicitly states a current role at a different company
- A recent authored or shared post clearly announces they joined another company after the portco hire date
- A current-role statement at a different company is clearly newer than the portco hire date

### Not Strong Enough On Its Own

These should usually lead to `Uncertain`, not a definitive status:

- LinkedIn top-card company alone
- old or partially rendered experience blocks without clear chronology
- profile headlines that may be stale or ambiguous
- likes or reactions to company posts
- internal CRM org mappings alone
- `paradigmdb` `Person.primaryOrganizationId` alone

## Date-Aware Rules

The timing of evidence matters.

If a LinkedIn company or role could plausibly predate the portco hire, do not treat it as proof the person left the portco.

Examples of invalid logic:

- `Top card says Saltmine, so Arthur Nelson left Noble`
- `Top card says OpenSea, so Robert Sun left Noise`

If the visible experience data suggests the company may have ended before the portco hire date, mark the row `Uncertain` unless stronger post-hire evidence exists.

## Status Assignment Rules

Use these exact buckets:

- `Still there`: strong post-hire evidence supports the portco as current employer
- `Left`: strong post-hire evidence supports a different current employer
- `Uncertain`: the evidence is stale, conflicting, incomplete, or merely suggestive

When in doubt, choose `Uncertain`.

## Recommended Output Columns

- person
- hire_date
- hired_company
- hired_role
- status
- current_company
- confidence
- validation_source
- evidence
- notes

## Recommended Confidence Levels

- `High`: explicit current-role or current-company statement
- `Medium`: strong but indirect post-hire evidence, such as recent company-specific authored activity
- `Low`: suggestive evidence only; usually pair with `Uncertain`

## Output Format

Lead with a short summary:

- total hires reviewed
- verified still there
- verified left
- uncertain

Then provide:

1. A table of verified movers
2. A table of verified still-there people
3. A note that the remaining rows are `Uncertain`
4. A CSV attachment or full table with evidence notes for every row

## Working Notes

- Say explicitly which sources were used
- Say explicitly why a row is `Uncertain`
- Preserve unresolved historical HIRE rows with no linked candidate rather than dropping them
- If a source is unavailable or rate-limited, say so and do not silently downgrade standards

## Example Decision Logic

- `LinkedIn top card == portco`, but no explicit current-role evidence: `Uncertain`
- `LinkedIn top card != portco`, but the visible experience may predate the hire: `Uncertain`
- `About says "Chief Legal Officer at Omaze"` after a Uniswap hire: `Left`
- `Recent public post says "Conduit is hiring multiple Protocol Engineers!" from the candidate's own account after a Conduit hire: `Still there`

## Example Prompt

Use this skill when the user says things like:

- "Give me talent placement updates for our portfolio hires"
- "Which of the people we placed are still there?"
- "Validate who left and where they went"
- "Track our network movement across portfolio companies"
