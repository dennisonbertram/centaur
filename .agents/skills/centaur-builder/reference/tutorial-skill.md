# Tutorial: Building a Skill

End-to-end walkthrough: write a skill locally, test it with your local AI coding tool, deploy it to Centaur, and verify it works.

We'll build a skill that teaches Centaur how to do a competitor analysis.

---

## What is a skill?

A skill is just a markdown file with instructions — a recipe card. When Centaur loads a skill, it follows the instructions step by step. No Python required.

---

## Step 1: Create the skill locally

Create a directory on your machine:

```bash
mkdir -p my-hackathon-skill/competitor-analysis
cd my-hackathon-skill/competitor-analysis
```

Create **`SKILL.md`**:

```markdown
---
name: competitor-analysis
description: "Analyzes competitors for a given company or product. Use when asked to research competitors, do competitive analysis, or compare market players."
---

# Competitor Analysis

Researches and summarizes the competitive landscape for a company or product.

## When To Use

Use when the user asks to:
- "analyze competitors for X"
- "who competes with X?"
- "competitive landscape for X"
- "compare X vs Y vs Z"

## Steps

1. **Clarify scope**: Ask the user what company/product to analyze and what industry it's in (if not obvious).

2. **Research competitors**: Use web search to find the top 5-10 competitors:
   ```
   call websearch search '{"query": "<company> competitors 2026"}'
   call websearch search '{"query": "<industry> market landscape"}'
   ```

3. **Gather details**: For each competitor, search for:
   - What they do (one-line description)
   - Funding / valuation (if available)
   - Key differentiator vs the target company
   ```
   call websearch search '{"query": "<competitor> funding valuation 2026"}'
   ```

4. **Present findings**: Output a summary table:

   | Competitor | What They Do | Funding | Key Differentiator |
   |-----------|-------------|---------|-------------------|
   | Acme Corp | Widget platform | $50M Series B | Enterprise focus |
   | Beta Inc  | Widget API   | $20M Series A | Developer-first   |

5. **Analysis**: Below the table, provide:
   - 2-3 sentence summary of the competitive landscape
   - Where the target company is positioned (leader, challenger, niche)
   - Any gaps or opportunities

## Output Rules

- Lead with the table, then the analysis
- Keep it concise — one Slack message, not a report
- Include source links where available
- If data is uncertain, say so — don't make up funding numbers
```

---

## Step 2: Test it locally

### Option A: Test with Amp or Claude Code

If you have Amp or Claude Code installed, copy the skill to your local skills directory:

```bash
# For Amp
mkdir -p ~/.config/agents/skills/competitor-analysis
cp SKILL.md ~/.config/agents/skills/competitor-analysis/

# For Claude Code
mkdir -p ~/.claude/skills/competitor-analysis
cp SKILL.md ~/.claude/skills/competitor-analysis/
```

Then open a new Amp/Claude Code session and say:

> "Load the competitor-analysis skill and analyze competitors for Figma."

The agent should follow your skill's steps. Watch how it interprets your instructions — this is your iteration loop. If it misses a step or formats output wrong, edit the SKILL.md and try again.

### Option B: Test via the Centaur API

You can also test by asking a Centaur agent to follow your instructions directly (before deploying):

```bash
export CENTAUR_API_KEY="aiv2_your_key_here"
THREAD_KEY="test-skill-$(date +%s)"

SPAWN=$(curl -s -X POST https://svc-ai.dayno.xyz/agent/spawn \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: $CENTAUR_API_KEY" \
  -d "{\"thread_key\":\"${THREAD_KEY}\",\"harness\":\"amp\"}")
AG=$(echo "$SPAWN" | python3 -c "import sys,json; print(json.load(sys.stdin)['assignment_generation'])")

# Paste the skill instructions directly into the message
SKILL_CONTENT=$(cat SKILL.md)
MSG="Follow these instructions exactly:

${SKILL_CONTENT}

Now: analyze competitors for Figma."

curl -s -X POST https://svc-ai.dayno.xyz/agent/message \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: $CENTAUR_API_KEY" \
  -d "{\"thread_key\":\"${THREAD_KEY}\",\"assignment_generation\":${AG},\"role\":\"user\",\"parts\":[{\"type\":\"text\",\"text\":$(python3 -c "import json,sys; print(json.dumps(sys.argv[1]))" "$MSG")}]}"

EXECUTE=$(curl -s -X POST https://svc-ai.dayno.xyz/agent/execute \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: $CENTAUR_API_KEY" \
  -d "{\"thread_key\":\"${THREAD_KEY}\",\"assignment_generation\":${AG},\"harness\":\"amp\",\"delivery\":{\"platform\":\"dev\"}}")
EXECUTION_ID=$(echo "$EXECUTE" | python3 -c "import sys,json; print(json.load(sys.stdin)['execution_id'])")

curl -s -N "https://svc-ai.dayno.xyz/agent/threads/${THREAD_KEY}/events?execution_id=${EXECUTION_ID}&after_event_id=0" \
  -H "X-Api-Key: $CENTAUR_API_KEY"
```

Review the output. Did the agent follow all 5 steps? Is the table formatted correctly? Iterate on the SKILL.md until you're happy.

---

## Step 3: Deploy to Centaur

Once your skill works well, deploy it:

```bash
THREAD_KEY="deploy-skill-$(date +%s)"
SKILL_CONTENT=$(cat SKILL.md)

SPAWN=$(curl -s -X POST https://svc-ai.dayno.xyz/agent/spawn \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: $CENTAUR_API_KEY" \
  -d "{\"thread_key\":\"${THREAD_KEY}\",\"harness\":\"amp\"}")
AG=$(echo "$SPAWN" | python3 -c "import sys,json; print(json.load(sys.stdin)['assignment_generation'])")

MSG="Add a new skill called 'competitor-analysis' to paradigmxyz/centaur.

Create the file .agents/skills/competitor-analysis/SKILL.md with this content:

${SKILL_CONTENT}

Then open a PR and merge it."

curl -s -X POST https://svc-ai.dayno.xyz/agent/message \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: $CENTAUR_API_KEY" \
  -d "{\"thread_key\":\"${THREAD_KEY}\",\"assignment_generation\":${AG},\"role\":\"user\",\"parts\":[{\"type\":\"text\",\"text\":$(python3 -c "import json,sys; print(json.dumps(sys.argv[1]))" "$MSG")}]}"

EXECUTE=$(curl -s -X POST https://svc-ai.dayno.xyz/agent/execute \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: $CENTAUR_API_KEY" \
  -d "{\"thread_key\":\"${THREAD_KEY}\",\"assignment_generation\":${AG},\"harness\":\"amp\",\"delivery\":{\"platform\":\"dev\"}}")
EXECUTION_ID=$(echo "$EXECUTE" | python3 -c "import sys,json; print(json.load(sys.stdin)['execution_id'])")

curl -s -N "https://svc-ai.dayno.xyz/agent/threads/${THREAD_KEY}/events?execution_id=${EXECUTION_ID}&after_event_id=0" \
  -H "X-Api-Key: $CENTAUR_API_KEY"
```

---

## Step 4: Verify it works

After the PR merges, the skill is available to all Centaur agents. Test it by asking an agent to use it:

```bash
THREAD_KEY="verify-skill-$(date +%s)"

SPAWN=$(curl -s -X POST https://svc-ai.dayno.xyz/agent/spawn \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: $CENTAUR_API_KEY" \
  -d "{\"thread_key\":\"${THREAD_KEY}\",\"harness\":\"amp\"}")
AG=$(echo "$SPAWN" | python3 -c "import sys,json; print(json.load(sys.stdin)['assignment_generation'])")

curl -s -X POST https://svc-ai.dayno.xyz/agent/message \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: $CENTAUR_API_KEY" \
  -d "{\"thread_key\":\"${THREAD_KEY}\",\"assignment_generation\":${AG},\"role\":\"user\",\"parts\":[{\"type\":\"text\",\"text\":\"Load the competitor-analysis skill and analyze competitors for Notion.\"}]}"

EXECUTE=$(curl -s -X POST https://svc-ai.dayno.xyz/agent/execute \
  -H "Content-Type: application/json" \
  -H "X-Api-Key: $CENTAUR_API_KEY" \
  -d "{\"thread_key\":\"${THREAD_KEY}\",\"assignment_generation\":${AG},\"harness\":\"amp\",\"delivery\":{\"platform\":\"dev\"}}")
EXECUTION_ID=$(echo "$EXECUTE" | python3 -c "import sys,json; print(json.load(sys.stdin)['execution_id'])")

curl -s -N "https://svc-ai.dayno.xyz/agent/threads/${THREAD_KEY}/events?execution_id=${EXECUTION_ID}&after_event_id=0" \
  -H "X-Api-Key: $CENTAUR_API_KEY"
```

---

## Tips for good skills

- **Be specific**: "Search for X using `call websearch search`" is better than "research X"
- **Show the output format**: include an example table or structure
- **Set guardrails**: "If data is uncertain, say so" prevents hallucination
- **Keep it under 500 lines**: split large reference material into `reference/` subdirectory files
- **Test with different inputs**: try your skill with 3-4 different companies/topics to make sure the instructions are general enough

---

## Adding scripts to a skill

Skills can include helper scripts for complex logic:

```
.agents/skills/my-skill/
├── SKILL.md
└── scripts/
    └── analyze.py    # Python helper
```

In your SKILL.md, reference it: "Run `scripts/analyze.py --input <data>` to process the results."

---

## Checklist

- [ ] SKILL.md has valid frontmatter (`name` matches directory, `description` includes trigger phrases)
- [ ] Instructions are clear enough that an AI can follow them without ambiguity
- [ ] Tested locally or via API — agent follows all steps correctly
- [ ] Output format is specified (table, bullet list, etc.)
- [ ] Deployed via agent and verified by asking a Centaur agent to use it
