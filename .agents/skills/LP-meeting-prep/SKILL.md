---
name: LP-meeting-prep
description: "Generates a pre-meeting briefing memo for a client or prospect meeting. Use when asked to prepare a briefing, write a meeting brief, prep for a meeting, or summarize who we're meeting with."
---

# Pre-Meeting Briefing Memo

Researches and writes a structured briefing memo before a client or prospect meeting.

## When To Use

Use when the user asks to:
- "prep a briefing for my meeting with X"
- "write a briefing memo for [name/org]"
- "help me prep for my meeting with X"
- "who are we meeting with tomorrow?"
- "briefing note for [name]"

## Inputs Needed

Ask the user if not already provided:
- **Who** is the meeting with? (person name + organization)
- **When** is the meeting? (date/time)
- **Where** — Zoom or in-person?

If the user says "check my calendar" or "you figure it out," use Google Calendar to find the next upcoming meeting and infer the details.

## Approach: Fast, Parallel, Draft First

**HARD TIME BUDGET: 5 minutes total. At 4 minutes, STOP researching and write the memo with whatever you have — even if some sections are sparse.**

Rules (not suggestions):
- **Fire ALL lookups in a single parallel tool-call batch.** Do not wait for one to finish before starting the next. Do not chain. One batch, many tools.
- **One attempt per lookup. No retries. No follow-ups.** If a tool errors, returns nothing, or returns partial data, move on. Do not investigate. Do not refine the query. Do not try an alternate source unless the original explicitly failed with an auth or 404 error and an alternate is named in the step below.
- **Do not think between tool calls.** No interpretation, summarization, or planning in between. Fire the batch, wait, collect, write.
- **Do not do "nice to have" deep dives.** If you catch yourself considering a follow-up search, stop and write the memo.
- **If any single tool takes longer than 90 seconds, abandon it.** Write "not available" for that section and proceed.

Budget guideline: calendar lookup ~30s, parallel lookup batch ~2min, memo assembly ~1min. Anything beyond that is over-research.

## Entity Precision

**Always be precise about which organization you are researching.** Many LPs operate under a parent brand with distinct subsidiaries — these are different entities with different relationships, attendees, and investment mandates. For example, Mubadala Capital Solutions is a distinct platform from Mubadala Capital and from Mubadala Investment Company. When searching for prior meetings, relationship data, and sizing, search specifically for the named entity (e.g. "Mubadala Capital Solutions") — do not conflate results from the broader parent organization unless explicitly relevant. Note any parent/subsidiary relationship in the LP overview section.

## Steps

### 1. Pull the calendar event

Search Google Calendar for the meeting to confirm:
- Date and time (convert to Pacific Time)
- Zoom link or location (in-person)
- Paradigm attendees — **list EVERY @paradigm.xyz email on the invite regardless of RSVP status** (accepted, needsAction, tentative, declined all count). Do not limit to only "accepted" responses; people often attend without formally accepting.
- LP/prospect attendees — **list EVERY external email on the invite regardless of RSVP status**

**Filtering rules — apply ONLY after the full attendee list is collected:**
- **Paradigm side:** Exclude Holly Morgan-Winsdale and Nicki Lardieri — they are EAs who handle scheduling, not meeting participants. Do NOT exclude anyone else on the Paradigm side — keep all other @paradigm.xyz attendees even if their RSVP is not "accepted."
- **LP/client side:** If any external attendee appears to be an EA or scheduler (e.g., they coordinated logistics with Holly or Nicki rather than being a substantive meeting participant), exclude them from LP attendees. Use email or calendar context to identify schedulers when ambiguous.

### 2. Run remaining lookups in parallel

Simultaneously look up:

**a. Organization research** — Search the internet for the specific entity's website. Write 3–5 sentences describing the business in substantive detail: what they actually do, investment mandate and strategies, asset classes covered, and any notable scale/AUM figures.

**Inclusion rules:**
- **Ownership structure:** Only include if it is prominently featured on the client org's own website (e.g. "wholly owned by X" displayed on their About page). If their site does not highlight ownership, leave it out.
- **Recent news:** Only include if it is a very big deal — examples: new CIO or senior management change, major M&A, large fund close, regulatory/legal headline. Skip routine news, partnerships, product launches, etc.

Example of the right shape when ownership and news both qualify: "Mubadala Capital Solutions is an alternative asset manager wholly owned by Mubadala Investment Company that manages capital on behalf of third-party investors. The platform invests across [asset classes] through both direct investments and fund-of-funds strategies. It was founded in [year] and has [AUM/deployed capital figure]." Substitute actual facts for the entity you're researching.

**b. LP relationship data** — Query `paradigmdb` using `db_tables` then `db_query` to find NAV and commitment by fund for this specific entity. If not found, try `addepar` (`list_entities` then portfolio data).

**c. Potential sizing** — Check the fundraising spreadsheet at https://docs.google.com/spreadsheets/d/1ZeYXnEjTEEDpJuLuYevgO8Xhj-H7tx7JnwcSU4a-X1A/edit?gid=1817261879#gid=1817261879, columns H–I (sizing) and J (firm vs. estimate — if closed or IOI confirmed, it is NOT an estimate).

**d. Purpose and agenda** — Search Slack and Gmail for recent threads mentioning the specific organization name or attendee names. Look for why this meeting is happening and any pre-discussed agenda.

**e. LP attendee research** — For each external attendee: find their LinkedIn profile URL, title, and prior organizations/roles. If LinkedIn is not found, search public bios on the organization's website, speaker profiles, conference pages, and press mentions — and link to whichever of those is the best available source. Do NOT explicitly note that LinkedIn was not found; simply use the best profile URL you have.

**f. Meeting history** — Look up the organization in Attio and pull its associated meetings/interactions list. Attio maintains a complete log of prior meetings tied to each org record, so a single Attio query is sufficient — do not cross-reference Google Calendar, Granola, or Notion. Use **this specific entity** (not the broader parent organization unless they are the same). List the 3 most recent touchpoints with: date, who from the org, who from Paradigm, and any associated Attio notes summary. Also note if any Paradigm attendee for this meeting has previously met the specific LP attendees (visible from the same Attio record).

### 3. Assemble the memo

Output the briefing in exactly this format:

---

**[Client/Prospect Name]**

([Zoom or In-Person]) at [Time, Day Month Year]

**Purpose:**
- [1–2 bullets from Slack/email context]

**Proposed agenda:**
- [1–2 bullets from Slack/email context]

**Paradigm attendees:**
- [Name]
- [Name]

**LP overview and relationship:**
- [3–5 sentence substantive description of the entity: ownership, mandate, strategies, asset classes, scale, notable news]
- Existing investments: [NAV + commitment by fund, OR "none" if no existing investments found]
- Potential sizing: [amount from spreadsheet, note if firm or estimate, OR "unknown" if not found]

**LP attendees:**
- [Hyperlinked Name](best available profile URL) ([prior org / time there if available])

**Prior meetings:**
- [Date] — [who from org] + [who from Paradigm]
  - [Key focus area from Attio notes if available]
- [Date] — [who from org] + [who from Paradigm]
- [Date] — [who from org] + [who from Paradigm]
- [Whether any Paradigm attendee above has met the specific LP attendees before]

(If no prior meetings found, the entire section is just: "**Prior meetings:** none")

---

## Output Rules

- Keep it tight — this is a memo, not a report
- **Always format meeting times in Pacific Time (PT)** — convert from whatever timezone the calendar event is stored in. Use "PT" as the label (e.g. "11:30 AM PT")
- Hyperlink LP attendee names to their best available public profile (LinkedIn preferred; fall back to org bio page, speaker profile, or press article). Do not mention the absence of LinkedIn.
- **Use concise fallback language** when data is missing:
  - No existing investments → "none"
  - No potential sizing found → "unknown"
  - No prior meetings found → "none"
  - Do NOT write "not found in [source]" in the final memo — that is internal research language
- If sizing is confirmed (closed or IOI), do NOT label it as an estimate
- Do not invent meeting notes or relationship history — only include what you find
