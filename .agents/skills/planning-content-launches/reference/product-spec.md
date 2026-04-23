# Content Growth OS

## One-Line Product

Slack-first operating system that turns any Paradigm content draft into a concrete launch brief: sharper thesis, better packaging, smarter channel choices, cleaner amplification sequencing, and a simple measurement plan.

## Problem

Paradigm produces strong content, but the work to maximize reach is still fragmented. Teams need a consistent way to answer:
- what is the core claim?
- who is this for?
- which channels actually matter?
- what supporting assets make it travel?
- who should amplify it, when, and how?

Without a shared system, high-quality content risks underperforming because packaging, sequencing, and follow-up are improvised.

## Users

- communications and brand team
- investing and research partners
- policy team
- program and events owners
- founders or operators asking for help packaging a launch

## Product Principles

- substance first, never engagement bait
- optimize for the right audience and trust, not vanity metrics
- treat every strong piece as a reusable content system, not a one-off asset
- make channel choices based on fit, not habit
- keep the workflow simple enough that teams will actually use it

## Core Workflow

Input:
- draft, link, or short brief
- launch goal
- target audiences
- timing
- accounts available to amplify
- assets already available

Decision engine:
- classify the content archetype
- sharpen the thesis and "why now"
- rank the audiences
- choose primary and secondary channels
- identify the minimum supporting assets that materially improve outcomes
- plan the launch sequence and metrics

Output:
- one `Launch Brief`
- optional `Preflight` feedback mode
- optional `Postmortem` mode after launch

## V1 Output

The shipped artifact is a single launch brief with:
- core thesis
- audience priorities
- goal ladder
- channel recommendations
- asset matrix: must have / should have / optional
- launch sequence: T-24h, launch, +6h, +24h, +72h
- success metrics
- risks and missing pieces

## Content Archetypes

V1 should handle:
- major announcements
- essays and thought pieces
- policy papers and amicus briefs
- dashboards and data launches
- fellowships, programs, and events
- product updates

## Why This Wedge

This is the highest-usage version because it fits existing behavior. Teams already share drafts and ask for launch feedback in Slack. A skill that returns a clean, reusable launch brief is easier to adopt than a full scheduling platform, analytics suite, or generic marketing copilot.

## Centaur Implementation

Ship in this order:
1. Skill: `planning-content-launches`
2. Reference spec and playbook inside the skill directory
3. Later: workflow to export a brief, schedule reminders, and capture postmortems
4. Later: lightweight web app for structured intake and brief history

## Success Metrics

Near term:
- repeated weekly usage by multiple teams
- faster turnaround from draft to launch plan
- more consistent use of supporting assets and follow-up replies

Longer term:
- more high-signal replies, citations, speaking invites, and qualified inbound conversations
- better reuse of one core piece into multiple strong native assets
- clearer institutional playbook for what works with each audience

## Non-Goals For V1

- not an auto-posting engine
- not a full attribution dashboard
- not a generic social media scoring bot
- not a replacement for editorial judgment

## Product Name

Working name: `Content Growth OS`

Shipped skill name: `planning-content-launches`
