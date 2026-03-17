---
name: policy-gigabrain
description: "Policy team intelligence system for Hill briefings, staffer tracking, bill analysis, vote prediction, and legislative trend detection. Use when asked about congressional meetings, staffers, legislation, regulatory actions, rulemakings, whip counts, policy team workflows, or any question about OCC, SEC, CFTC, FDIC, FinCEN, Treasury guidance, stablecoins, GENIUS Act, market structure bills, or crypto regulation. Triggers on: policy question, regulatory impact, bill analysis, legislation impact on portfolio."
---

# Policy Gigabrain

Centralized intelligence system for government affairs. Generates meeting briefers, tracks staffers and legislators, monitors legislation, predicts votes, and surfaces portfolio-relevant regulatory actions.

## ⚠️ MANDATORY FIRST STEP: Policy Explainer Index

**Before answering ANY policy or regulatory question — before running web searches or reading external sources — you MUST first check the Paradigm Policy team's internal analysis.**

```bash
call gsuite docs_read '{"doc_id":"1yiKL4NgJfT0cAXehqHvaYC1mMezKdDhxwnr8Gm8aa6c"}'
```

This is the **Policy Explainer Index** ([link](https://docs.google.com/document/d/1yiKL4NgJfT0cAXehqHvaYC1mMezKdDhxwnr8Gm8aa6c/edit?tab=t.0)), maintained by the Policy team. It contains Paradigm's internal analysis and takes on major regulatory developments (GENIUS Act, FDIC rulemakings, SEC actions, etc.).

**Why this matters:** The Policy team's analysis includes Paradigm-specific context, portfolio impact assessments, and strategic framing that external sources cannot provide. External web searches should only supplement — never replace — the team's own work.

**Workflow:**
1. Read the Policy Explainer Index to check if the topic has been analyzed
2. If an explainer exists, read the linked analysis doc for full detail
3. Pull recent posts from **#gigabrain-feed** for additional policy intel:
   ```bash
   call slack get_channel_history '{"channel":"C0AM0TR8N91","limit":50}'
   ```
4. Only then supplement with external sources (OCC/SEC/CFTC websites, Federal Register, etc.) if needed
5. Always cite the internal analysis as the primary source

## Core Capabilities

| Function | Description |
|----------|-------------|
| **Meeting Briefers** | Auto-generate one-pagers for Hill meetings |
| **Staffer Tracking** | Track congressional/regulatory staff careers and relationships |
| **Bill Tracking** | Monitor legislation with momentum scores and status |
| **Vote Prediction** | Maintain whip sheets with stance, confidence, rationale |
| **Trend Detection** | Surface emerging patterns across jurisdictions |
| **Portfolio Impact** | Flag legislation affecting portfolio companies |

---

## Data Sources

### External APIs

| Source | Tool | Purpose |
|--------|------|---------|
| **Congress.gov** | `call congress` | Bills, members, committees, hearings, votes, amendments |
| **Federal Register** | `call fedreg` | Regulatory dockets, comment periods, rulemakings |
| **OpenFEC** | `call openfec` | Campaign contributions, candidates, committees, filings |
| **LegiStorm** | `call legistorm` | Congressional staff (`get_staff`), members (`get_members`), hearings (`get_hearings`), offices (`get_offices`), caucuses (`get_caucuses`), town halls (`get_townhalls`), privately funded travel (`get_trips`). All list endpoints require `updated_from`/`updated_to` date params (YYYY-MM-DD). |
| **Plural (Open States)** | `call plural` | State-level legislation (`search_bills`, `get_bill`), legislators (`search_people`), committees (`list_committees`), and legislative events (`list_events`). Use `jurisdiction` param (e.g. `"New York"`, `"California"`). Covers all 50 states + territories. |

### Internal Sources

| Source | Tool | Use For |
|--------|------|---------|
| **Shift / paradigmdb** | `call paradigmdb` | Portfolio companies, prior interactions, notes |
| **Slack** | `call slack search_messages` | Policy team discussions, intel |
| **#gigabrain-feed** | `call slack get_channel_history '{"channel":"C0AM0TR8N91"}'` | Curated policy intel feed — regulatory updates, legislative signals, and policy analysis posted by the policy team. Check this channel early in any policy workflow. |
| **GSuite** | `call gsuite` | Meeting notes, Hill interaction logs, Drive docs |
| **Archived docs / notes** | `call gsuite`, `call slack search_messages`, `call websearch search` | Archived policy documents, notes, and discussion |

---

## Workflows

### 1. Meeting Briefer Generation

Generate a policy briefing memo before Hill meetings.

**Trigger Phrases** (from Madison, Alex G., Justin, Stefan, Katie, or Caitlin):
- "Write a policy briefing memo for [Name, Title]"
- "Briefing memo for [Name]"
- "Policy briefer for [Name]"
- "Meeting brief for [Name]"

**Input:** Member/staffer name, meeting context, date

**Steps:**
1. Look up member profile via web search and LegiStorm:
   ```bash
   # LegiStorm member profile, committee assignments, staff
   call legistorm get_members '{"updated_from":"2025-01-01","updated_to":"2026-12-31","state_id":"[XX]"}'
   ```
2. Search internal sources for prior Paradigm interactions:
   ```bash
   call slack search_messages '{"query":"from:#policy [member_name]"}'
   call slack search_messages '{"query":"in:#gigabrain-feed [member_name]"}'
   call gsuite gmail_search '{"query":"[member_name]"}'
   call paradigmdb notes_search '{"query":"[member_name]"}'
   ```
3. Find relevant pending legislation:
   ```bash
   call congress bills '{"congress":119}'
   call congress bill '{"congress":119,"type":"s","number":123}'
   ```
4. Check FEC for campaign contribution context:
   ```bash
   call openfec candidates '{"name":"[member_name]"}'
   call openfec contributions '{"contributor_name":"[member_name]"}'
   ```
5. Cross-reference with paradigmdb for portfolio company relevance:
   ```bash
   call paradigmdb db_query '{"query":"SELECT * FROM \"Organization\" WHERE name ILIKE '\''%relevant_company%'\'';"}'
   ```
6. Generate structured briefer (see template below)

**Briefer Template:**
```
# Policy Briefing Memo: [Name, Title]
Date: [DATE] | Location: [LOCATION]

## Executive Summary
[2-3 sentence overview: who we're meeting, why it matters, and our primary objective.]

## Background
Write 1-2 paragraphs in full sentences covering: their current role and title, committee assignments, party and state, what they are currently prioritizing, key legislation they sponsor or co-sponsor, and any prior Paradigm interactions or touchpoints.

## Biography
Write 1-2 paragraphs in full sentences covering: key career milestones (Hill tenure, private sector, executive branch experience), education and alma mater, notable past and present committee or subcommittee positions, leadership roles, and relevant personal context such as state/district dynamics, known interests, or relationship dynamics.

## Crypto Knowledge
Write 1-2 paragraphs in full sentences covering: their overall familiarity level with crypto and digital assets, notable public statements or positions on crypto, DeFi, or stablecoins, relevant votes on crypto or fintech legislation, and the sophistication level of key staffers covering crypto and tech policy.

## Stance on Prediction Markets
Write 5-7 sentences covering: (1) the member's general opinion of prediction markets (public statements, letters signed, bills sponsored or co-sponsored); (2) relevant current events such as prediction market bills introduced, CFTC rulemakings, or court cases (e.g., Kalshi litigation); (3) whether those current events are likely to shift the member's position; and (4) any constituent, state, or district considerations that could influence their stance — including state gambling revenue, tribal gaming interests, state gambling laws, DGE/gaming commission enforcement actions, and the competitive dynamics between CFTC-regulated event contracts and state-licensed sportsbooks. Frame the analysis around Paradigm's position that prediction markets and all event contracts (including sports betting) should be regulated by the CFTC under exclusive federal jurisdiction.

## Goals
- **Primary Ask:** [What we want from this meeting]
- **Secondary Objectives:** [Relationship-building goals, intel to gather, positions to reinforce]
- **Success Criteria:** [How we'll know the meeting went well]

## Specific Topics To Address
1. [Topic 1 — context, our position, and suggested framing]
2. [Topic 2 — context, our position, and suggested framing]
3. [Topic 3 — context, our position, and suggested framing]
[Add as many as needed based on the meeting agenda and current legislative landscape]
```

### 2. Staffer Tracking

Track congressional and regulatory staffers relevant to crypto policy.

**Key Roles to Track:**
- Legislative Directors (LD)
- Committee Counsel (especially Banking, Finance, Agriculture)
- Personal Office Chiefs of Staff
- Leadership Staff
- Executive branch personnel rotating to legislative

**Data Points:**
- Current role and office
- Committee assignments
- Policy areas covered
- Career trajectory
- Paradigm touchpoints
- Alma mater (for relationship mapping)

**Flags to Surface:**
- Junior staff moving to senior roles (build relationships early)
- Committee transfers (new jurisdictional exposure)
- Executive → legislative rotations
- Departures from key offices

**Search Commands:**
```bash
# Find prior interactions with staffer
call slack search_messages '{"query":"[staffer_name]"}'
call gsuite gmail_search '{"query":"[staffer_name]"}'

# Check if mentioned in notes
call paradigmdb notes_search '{"query":"[staffer_name]"}'

# LegiStorm lookup — get_staff requires date range; use a wide window to find current staff
call legistorm get_staff '{"updated_from":"2025-01-01","updated_to":"2026-12-31","member_id":[member_id]}'
# Or search all recent staff updates
call legistorm get_staff '{"updated_from":"2026-01-01","updated_to":"2026-12-31","limit":20}'
```

### 3. Bill Tracking & Analysis

Monitor crypto-relevant legislation across federal and state jurisdictions.

**Federal Focus:**
- Senate Banking Committee
- House Financial Services Committee
- Agriculture Committees (CFTC jurisdiction)
- Judiciary Committees (DOJ, IP)

**State Priorities:** NY, TX, CA, WY, IL (active crypto agendas)

**Track Per Bill:**
- Bill number and title
- Sponsors and cosponsors
- Committee referral and status
- Hearing schedule
- Markup dates
- Floor action timeline
- Amendment activity
- Paradigm position (support/oppose/monitor)

**Search Commands:**
```bash
# Search federal bills via Congress.gov API
call congress bills '{"congress":119,"limit":50}'
call congress bill '{"congress":119,"type":"hr","number":4763,"detail":"summaries"}'

# Search federal hearings
call congress hearings '{"congress":119,"chamber":"senate"}'
call legistorm get_hearings '{"updated_from":"2026-01-01","updated_to":"2026-12-31","chamber":"S"}'
call legistorm get_townhalls '{"updated_from":"2026-01-01","updated_to":"2026-12-31"}'

# Search STATE-LEVEL bills via Plural (Open States)
call plural search_bills '{"jurisdiction":"New York","q":"cryptocurrency","sort":"updated_desc"}'
call plural search_bills '{"jurisdiction":"California","q":"digital assets"}'
# Get specific state bill details
call plural get_bill '{"jurisdiction":"New York","session":"2025-2026","bill_id":"S1234"}'

# Search for internal discussions
call slack search_messages '{"query":"[bill number]"}'
```

### 4. Vote Prediction / Whip Sheet

Maintain running vote counts for priority legislation.

**Whip Sheet Fields:**
| Field | Values |
|-------|--------|
| Stance | Support / Lean Support / Uncommitted / Lean Oppose / Oppose |
| Strength | Firm / Soft |
| Rationale | Why we believe this |
| Key Influencer | Who can move them |
| The Ask | What we need from them |
| Next Action | Follow-up task |
| Owner | Paradigm team member |
| Last Verified | Date of last confirmation |
| Evidence | Meeting notes, public statements |

**Prediction Inputs:**
- Historical voting patterns (VoteSmart, GovTrack)
- Cosponsor networks
- Public statements
- Committee behavior
- Party leadership signals
- Direct intelligence from meetings

**Update Process:**
1. After each Hill interaction, log stance update
2. Flag inconsistencies between public statements and private positions
3. Surface members whose stance has shifted

### 5. Coalition & Opposition Mapping

Track who is lobbying on which bills.

**Entities to Track:**
- Industry groups (Chamber, trade associations)
- Advocacy organizations
- Companies (competitors, allies)
- Think tanks
- Other crypto firms

**Per Entity:**
- Position on key bills
- Lobbying intensity (high/medium/low)
- Key contacts
- Coalition membership

### 6. Trend Detection

Surface emerging patterns before they become consensus.

**Signals to Monitor:**
- Bill introduction clusters (3+ states with similar language)
- Hearing topic frequency
- Floor statement themes
- Regulatory action patterns
- Model legislation from ALEC, ULC

**State AG Actions:**
- Enforcement actions in priority states
- Settlement patterns
- New investigation announcements

**Search Commands:**
```bash
# Search Federal Register for crypto-related regulatory actions
call fedreg search '{"query":"cryptocurrency","agency":"securities-and-exchange-commission"}'
call fedreg search '{"query":"digital assets","agency":"commodity-futures-trading-commission"}'
call fedreg search '{"query":"stablecoin","type":"PRORULE"}'

# State-level legislation via Plural (Open States) — check priority states
call plural search_bills '{"jurisdiction":"New York","q":"cryptocurrency","action_since":"2026-01-01"}'
call plural search_bills '{"jurisdiction":"Texas","q":"digital assets","action_since":"2026-01-01"}'
call plural search_bills '{"jurisdiction":"California","q":"blockchain","action_since":"2026-01-01"}'
call plural search_bills '{"jurisdiction":"Wyoming","q":"digital assets","action_since":"2026-01-01"}'
call plural search_bills '{"jurisdiction":"Illinois","q":"cryptocurrency","action_since":"2026-01-01"}'

# State-level events (hearings, floor sessions)
call plural list_events '{"jurisdiction":"New York","after":"2026-01-01","require_bills":true}'

# LegiStorm for congressional hearing trends
call legistorm get_hearings '{"updated_from":"2026-01-01","updated_to":"2026-12-31","limit":20}'

# Supplement with web search
call websearch search '{"query":"state cryptocurrency legislation 2026"}'
```

### 7. Regulatory Docket Monitoring

Track SEC, CFTC, FinCEN, OCC, Treasury rulemakings.

**Per Docket:**
- Agency and docket number
- Proposed rule summary
- Comment deadline
- Paradigm response status (draft/submitted/none)
- Portfolio company impact

**Search Commands:**
```bash
# Open comment periods
call fedreg comments-open '{"agency":"securities-and-exchange-commission"}'
call fedreg comments-open '{"agency":"commodity-futures-trading-commission"}'

# Search regulatory dockets
call fedreg search '{"query":"cryptocurrency","type":"RULE"}'
call fedreg search '{"query":"digital assets","type":"PRORULE","agency":"treasury-department"}'

# Get specific document details
call fedreg document '{"document_number":"2026-01234"}'
```

### 8. Portfolio Impact Flagging

Automatically surface legislation affecting portfolio companies.

**Process:**
1. When analyzing new legislation, check if any provisions affect:
   - Stablecoin issuers
   - DeFi protocols
   - Custody providers
   - Exchange operators
   - Any specific portfolio company sector
2. Query paradigmdb for relevant holdings:
   ```bash
   call paradigmdb notes_search '{"query":"[sector keyword]"}'
   call paradigmdb db_query '{"query":"SELECT o.name, o.description FROM \"Organization\" o WHERE o.description ILIKE '\''%stablecoin%'\'';"}'
   ```
3. Flag with explanation of potential impact

---

## Jurisdiction Mapping

### Who Has the Pen?

| Issue | Primary Jurisdiction | Key Committees |
|-------|---------------------|----------------|
| Market structure | SEC | Senate Banking, House Financial Services |
| Derivatives | CFTC | Senate/House Agriculture |
| Stablecoins | Mixed (SEC/OCC/Fed) | Banking + Financial Services |
| AML/KYC | FinCEN | Banking, Homeland Security |
| Sanctions | OFAC/Treasury | Banking, Foreign Affairs |
| Tax | Treasury/IRS | Finance, Ways & Means |

### Committee Staff Routing

For a given issue, route to the right staffer:
1. **Committee Counsel** for legislative drafting
2. **Personal Office LD** for member positioning
3. **Leadership Staff** for floor scheduling and whip operations

---

## Internal Accountability

### Log All Hill Interactions

After every Hill meeting or call:
1. Log in Shift as meeting note
2. Record commitments made (by us and by them)
3. Note follow-ups owed
4. Update relevant whip sheet entries
5. Tag portfolio-relevant intel

### Periodic Reports

**Weekly:** Policy team activity summary
**Monthly:** Legislative landscape shifts, whip sheet changes
**Quarterly:** Strategic assessment for leadership

---

## Natural Language Queries

The system should answer questions like:

- "What is Senator X's likely position on the GENIUS Act and why?"
- "Which bills introduced this session could affect our stablecoin portfolio companies?"
- "Who are the key staffers on Senate Banking covering crypto?"
- "What have we heard about stablecoin reserve requirements in the last 90 days?"
- "Generate a briefer for my meeting with Rep Y tomorrow"
- "What is the current whip count on [bill]?"
- "Which states have introduced DeFi-related bills this year?"

---

## Example Session

**User:** Policy briefer for Senator Lummis — meeting tomorrow about stablecoin legislation.

**Agent:**
1. Read Policy Explainer Index first for internal analysis
2. Pull recent #gigabrain-feed posts for stablecoin intel:
   ```bash
   call slack get_channel_history '{"channel":"C0AM0TR8N91","limit":50}'
   ```
3. Look up Senator Lummis via LegiStorm and web search:
   ```bash
   call legistorm get_members '{"updated_from":"2025-01-01","updated_to":"2026-12-31","state_id":"WY"}'
   call legistorm get_staff '{"updated_from":"2025-01-01","updated_to":"2026-12-31","member_id":[lummis_member_id]}'
   ```
4. Search internal sources:
   ```bash
   call slack search_messages '{"query":"Lummis"}'
   call slack search_messages '{"query":"in:#gigabrain-feed Lummis"}'
   call gsuite gmail_search '{"query":"Lummis"}'
   call paradigmdb notes_search '{"query":"Lummis"}'
   ```
5. Find current stablecoin legislation — federal and state:
   ```bash
   call congress bills '{"congress":119}'
   call plural search_bills '{"q":"stablecoin","action_since":"2026-01-01"}'
   ```
6. Check portfolio companies in stablecoin space
7. Generate briefer using template

---

## Future Integrations

| Integration | Purpose | Priority |
|-------------|---------|----------|
| Shift direct integration | Portfolio cross-reference | Medium |
| Regulations.gov API | Docket comments, rulemaking tracking | Medium |
