---
name: sourcer
description: Talent sourcing agent that finds candidates matching a job description. Crawls LinkedIn, GitHub, and X/Twitter, then outputs a Google Sheet with candidate profiles. Use when asked to source candidates, find talent, or build a recruiting pipeline.
---

# Talent Sourcer Agent

Sources candidates from LinkedIn, GitHub, and X/Twitter based on a job description, then generates a Google Sheet with results.

## Workflow

### 1. Parse Job Description

Extract key requirements:
- **Role type** (engineering, product, design, operations, etc.)
- **Seniority level** (junior, senior, staff, principal, etc.)
- **Required skills/technologies**
- **Industry context** (crypto, fintech, AI, etc.)
- **Location preferences** (if any)

### 2. Build Search Strategy

Create searches targeting high-signal profiles:

| Signal | How to Find |
|--------|-------------|
| Elite universities | Search profiles with Stanford, MIT, Caltech, Harvard, Princeton, Yale, CMU, Berkeley, Oxford, Cambridge, etc. |
| High-growth companies | People at early-stage Uber, Stripe, Coinbase, OpenAI, Anthropic, etc. before 2016-2018 |
| GitHub activity | Use browser-use to find contributors to relevant repos |
| Twitter/X influence | `ptwittercli search` for people tweeting about relevant topics |

### 3. Location Filtering (Hard Requirement)

**If the job description specifies a location, only include candidates based in that location.**

- Check LinkedIn profile location field
- Check X/Twitter bio for city/region mentions
- Exclude candidates who don't match, regardless of other qualifications
- If JD says "Remote" or has no location, skip this filter

### 4. Candidate Ranking Criteria

**Rank candidates in this priority order:**

1. **Title Correspondence** (25%)
   - How closely does the candidate's current title match the target role?
   - Same function + same level = best match (e.g., "Trade Operations Associate" → "Trade Operations Manager")
   - Same function + different level = good match (e.g., "Senior Engineer" → "Staff Engineer")
   - Different function = poor match, even if skills align (e.g., "Trade Operations Associate" → "CFO" is a poor fit)
   - Weight functional alignment heavily over keyword/skill overlap

2. **Educational Foundation** (20%)
   - Elite university attendance (MIT, Stanford, CMU, Caltech, Harvard, Princeton, Yale, Berkeley, Oxford, Cambridge)
   - Consider admissions selectivity (< 10% acceptance = top tier)
   - Note: attendance matters more than graduation

3. **Professional Trajectory** (20%)
   - Impact achieved relative to years of experience
   - 3 years with senior-level impact >>> 7 years at average pace
   - Look for promotions, title progressions, scope expansions

4. **Talent Density of Organizations** (20%)
   - Exclusivity of teams they've worked on
   - Early employees at hypergrowth startups (Uber pre-2014, Stripe pre-2016, Coinbase pre-2017)
   - Elite teams: Jane Street, Two Sigma, Renaissance, Google Brain, DeepMind
   - Early Paradigm portfolio companies

5. **Timing Window** (15%)
   - When did they join high-performers?
   - Uber 2013 > Uber 2017
   - Coinbase 2015 > Coinbase 2020
   - Earlier = higher agency signal

### 4. Data Sources & Tools

#### LinkedIn (via browser-use)

```python
from browser_use import Agent, Browser, ChatBrowserUse
import asyncio

async def search_linkedin(query: str):
    browser = Browser(
        cloud_profile_id='paradigm-ai',
        cloud_proxy_country_code='us',
    )

    agent = Agent(
        task=f"""
        1. Navigate to https://www.linkedin.com
        2. Search for: {query}
        3. Filter by: People
        4. For each of the first 20 results, extract:
           - Full name
           - Current job title
           - Current company
           - Location/city
           - LinkedIn profile URL
           - Headline/summary
        5. Return as JSON
        """,
        browser=browser,
        llm=ChatBrowserUse(),
    )

    history = await agent.run(max_steps=50)
    return history.final_result()

asyncio.run(search_linkedin("software engineer stripe coinbase crypto"))
```

#### GitHub (via browser-use)

```python
async def search_github_contributors(repo: str):
    browser = Browser(
        cloud_profile_id='paradigm-ai',
        cloud_proxy_country_code='us',
    )

    agent = Agent(
        task=f"""
        1. Navigate to https://github.com/{repo}/graphs/contributors
        2. For top 30 contributors, extract:
           - GitHub username
           - Number of commits
        3. For each username, visit their profile and extract:
           - Full name (if available)
           - Location
           - Company
           - Email (if public)
           - Twitter handle (if linked)
        4. Return as JSON
        """,
        browser=browser,
        llm=ChatBrowserUse(),
    )

    history = await agent.run(max_steps=100)
    return history.final_result()
```

#### X/Twitter (via ptwittercli)

```bash
# Search for people discussing relevant topics
ptwittercli search "ethereum solidity from:* -filter:replies" -n 100

# Get profiles of influential accounts
ptwittercli user vitalik
ptwittercli followers paradigm -n 200
```

### 5. Email Discovery

Try these methods in order:

1. **GitHub profiles** - Often have public email
2. **Pattern matching** - firstname@company.com, firstname.lastname@company.com
3. **Hunter.io** (via browser-use) - Domain email patterns
4. **Apollo.io** (via browser-use) - Email enrichment

### 6. Output to Google Sheet

Create the sheet with `gsuite sheets create`:

```bash
# Create sheet with proper naming: "Sourcing target list: [role] [date]"
gsuite -a svc_ai@paradigm.xyz sheets create \
  --title "Sourcing target list: Senior Protocol Engineer 2026-02-04" \
  --share "dmccarthy@paradigm.xyz" \
  --role writer
```

**Required columns:**

| Column | Description |
|--------|-------------|
| Name | Full name |
| Title | Current job title |
| Company | Current company/organization |
| LinkedIn | Profile URL |
| Email | Email address (if found) |
| Location | City/geography |
| Score | Ranking score (1-100) |
| Notes | Key signals (university, prior companies, timing) |

Update the sheet with data:

```bash
gsuite -a svc_ai@paradigm.xyz sheets update \
  --spreadsheet-id "<SPREADSHEET_ID>" \
  --range "A1:H100" \
  --values '[["Name","Title","Company","LinkedIn","Email","Location","Score","Notes"],["Jane Doe","Staff Engineer","Stripe","https://linkedin.com/in/janedoe","jane@stripe.com","SF","95","MIT CS, Stripe 2015, ex-Google Brain"]]'
```

### 7. Example Full Workflow

```python
import asyncio
import subprocess
import json
from browser_use import Agent, Browser, ChatBrowserUse

async def source_candidates(job_description: str, role_name: str):
    """Full sourcing workflow"""

    # 1. Parse JD for search terms
    key_skills = extract_skills(job_description)  # Your parsing logic
    target_companies = ["stripe", "coinbase", "opensea", "uniswap", "paradigm"]

    candidates = []

    # 2. Search LinkedIn
    browser = Browser(cloud_profile_id='paradigm-ai', cloud_proxy_country_code='us')

    for company in target_companies:
        query = f"{key_skills[0]} {company} crypto blockchain"
        agent = Agent(
            task=f"Search LinkedIn for '{query}', extract first 20 profiles with name, title, company, location, LinkedIn URL",
            browser=browser,
            llm=ChatBrowserUse(),
        )
        history = await agent.run(max_steps=30)
        candidates.extend(parse_linkedin_results(history.final_result()))

    # 3. Search GitHub contributors
    relevant_repos = ["ethereum/go-ethereum", "paradigmxyz/reth", "foundry-rs/foundry"]
    for repo in relevant_repos:
        agent = Agent(
            task=f"Get top 20 contributors from github.com/{repo}/graphs/contributors with their profiles",
            browser=browser,
            llm=ChatBrowserUse(),
        )
        history = await agent.run(max_steps=40)
        candidates.extend(parse_github_results(history.final_result()))

    # 4. Search Twitter
    twitter_results = subprocess.run(
        ["ptwittercli", "search", f"{key_skills[0]} engineer building", "-n", "50"],
        capture_output=True, text=True
    )
    candidates.extend(parse_twitter_results(twitter_results.stdout))

    # 5. Score and dedupe
    scored = score_candidates(candidates)
    deduped = dedupe_by_name_or_email(scored)
    top_candidates = sorted(deduped, key=lambda x: x['score'], reverse=True)[:50]

    # 6. Create Google Sheet
    from datetime import date
    sheet_title = f"Sourcing target list: {role_name} {date.today()}"

    create_result = subprocess.run([
        "gsuite", "-a", "svc_ai@paradigm.xyz", "sheets", "create",
        "--title", sheet_title,
        "--share", "dmccarthy@paradigm.xyz",
        "--role", "writer"
    ], capture_output=True, text=True)

    spreadsheet_id = extract_spreadsheet_id(create_result.stdout)

    # 7. Populate sheet
    rows = [["Name", "Title", "Company", "LinkedIn", "Email", "Location", "Score", "Notes"]]
    for c in top_candidates:
        rows.append([
            c.get('name', ''),
            c.get('title', ''),
            c.get('company', ''),
            c.get('linkedin', ''),
            c.get('email', ''),
            c.get('location', ''),
            str(c.get('score', 0)),
            c.get('notes', '')
        ])

    subprocess.run([
        "gsuite", "-a", "svc_ai@paradigm.xyz", "sheets", "update",
        "--spreadsheet-id", spreadsheet_id,
        "--range", f"A1:H{len(rows)}",
        "--values", json.dumps(rows)
    ])

    return f"Created sheet: https://docs.google.com/spreadsheets/d/{spreadsheet_id}"

def score_candidates(candidates, target_title: str, target_location: str = None):
    """Score based on the 5 criteria, with location filtering"""
    elite_schools = {'mit', 'stanford', 'cmu', 'caltech', 'harvard', 'princeton', 'yale', 'berkeley', 'oxford', 'cambridge'}
    elite_companies = {
        'stripe': {'weight': 20, 'early_year': 2016},
        'coinbase': {'weight': 20, 'early_year': 2017},
        'uber': {'weight': 15, 'early_year': 2014},
        'openai': {'weight': 20, 'early_year': 2020},
        'anthropic': {'weight': 20, 'early_year': 2023},
        'jane street': {'weight': 20, 'early_year': None},
        'two sigma': {'weight': 20, 'early_year': None},
        'paradigm': {'weight': 20, 'early_year': None},
        'a16z crypto': {'weight': 20, 'early_year': None},
    }

    # Location filtering (hard requirement)
    if target_location and target_location.lower() not in ['remote', '']:
        candidates = [c for c in candidates if location_matches(c.get('location', ''), target_location)]

    for c in candidates:
        score = 25  # Base score
        notes = []

        # Title correspondence (25%) - functional alignment matters most
        title = (c.get('title', '') or '').lower()
        target_lower = target_title.lower()
        title_score = compute_title_match(title, target_lower)
        score += title_score
        if title_score >= 20:
            notes.append("title match")

        # Education (20%)
        edu = (c.get('education', '') or '').lower()
        for school in elite_schools:
            if school in edu:
                score += 20
                notes.append(f"{school.upper()}")
                break

        # Professional trajectory (20%) - infer from title vs years
        if 'staff' in title or 'principal' in title or 'director' in title:
            score += 18
            notes.append("senior title")
        elif 'senior' in title or 'lead' in title:
            score += 12

        # Talent density (20%) + Timing (15%)
        company = (c.get('company', '') or '').lower()
        for co_name, co_data in elite_companies.items():
            if co_name in company:
                score += co_data['weight']
                notes.append(co_name)
                break

        c['score'] = min(score, 100)
        c['notes'] = ', '.join(notes)

    return candidates

def location_matches(candidate_location: str, target_location: str) -> bool:
    """Check if candidate location matches target (case-insensitive, partial match)"""
    if not candidate_location:
        return False
    return target_location.lower() in candidate_location.lower()

def compute_title_match(candidate_title: str, target_title: str) -> int:
    """Score title correspondence (0-25 points)"""
    # Extract function words (operations, engineer, analyst, manager, etc.)
    functions = ['engineer', 'operations', 'analyst', 'manager', 'associate', 'director', 
                 'developer', 'designer', 'scientist', 'researcher', 'lead', 'head']
    
    candidate_funcs = [f for f in functions if f in candidate_title]
    target_funcs = [f for f in functions if f in target_title]
    
    # Same function = high score
    if set(candidate_funcs) & set(target_funcs):
        return 25
    # Adjacent functions (e.g., analyst/associate) = medium score
    adjacent_pairs = [{'analyst', 'associate'}, {'manager', 'director'}, {'lead', 'manager'}]
    for pair in adjacent_pairs:
        if (set(candidate_funcs) & pair) and (set(target_funcs) & pair):
            return 15
    # Different function = low score
    return 5
```

## Ideal Candidate Signals

- Extremely articulate communicator, can explain complex ideas in a way that is easy to understand (Strong signal)
- Multiple examples of solving complex problems (Strong signal)
- Followed by multiple people at Paradigm or by Paradigm founders/fellows on X/Twitter (Strong signal)
- Spend less than 1 year in each role over multiple companies (Yellow flag)

## Sourcing Heuristics

- Look for candidates who work at companies funded by the most prestigious VCs (Sequoia, Andreessen Horowitz, Founders Fund, Y Combinator, etc.)
- Omit anyone who currently works at a Paradigm portfolio company, but use people at companies like Phantom, Uniswap, Zora, Magic Eden, OpenSea, Axiom, Coinbase, Privy, Kalshi, Monad and Coinbase as examples of exceptional talent, with some caveats

## Decision Framework

- Would Dan McCarthy or Chris Shu feel comfortable recommending this candidate to a Paradigm portfolio company?
- Would this person accelerate a portfolio company's trajectory?
- Would we be interested in staying in touch with this person for a future role?

## Tips

- **Parallelize searches** - Run LinkedIn, GitHub, Twitter searches concurrently
- **Respect rate limits** - Space out browser-use requests to avoid blocks
- **Dedupe aggressively** - Same person may appear across platforms
- **Verify emails** - Pattern-matched emails should be marked as unverified
- **Prioritize recency** - More recent profiles have more accurate info

## Common Search Queries

| Role Type | LinkedIn Query | GitHub Repos | Twitter Search |
|-----------|---------------|--------------|----------------|
| Protocol Engineer | "solidity rust ethereum" | ethereum/*, paradigmxyz/*, foundry-rs/* | "solidity rust building" |
| Research Engineer | "machine learning crypto" | flashbots/*, paradigmxyz/* | "MEV research building" |
| Full-Stack Engineer | "react typescript crypto" | uniswap/*, opensea/* | "crypto frontend building" |
| Security Engineer | "smart contract audit" | crytic/*, trail-of-bits/* | "smart contract security" |
