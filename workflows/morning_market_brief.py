"""Workflow: delivers a dense morning market brief to Slack every trading day."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass, field
from typing import Any
from zoneinfo import ZoneInfo

from api.workflow_engine import WorkflowContext

WORKFLOW_NAME = "morning_market_brief"


@dataclass
class Input:
    equities: list[str] = field(default_factory=lambda: ["MSTR", "COIN", "HOOD", "NVDA", "MARA"])
    slack_channel: str = "morning-brief"
    timezone: str = "America/New_York"
    run_hour: int = 7
    run_minute: int = 30
    max_iterations: int = 0  # 0 = run forever


BRIEF_PROMPT = """IMPORTANT: Work efficiently. Follow these data-gathering steps first, then write the brief.

DATA GATHERING (do these in parallel where possible):
1. Visit https://finance.yahoo.com/ and extract the top market headlines, trending tickers, and market movers
2. Visit https://finance.yahoo.com/markets/ for SPX, NDX, DXY, VIX, gold, oil, bond yields, USDJPY levels
3. Visit https://finance.yahoo.com/markets/crypto/ for BTC, ETH, SOL prices and crypto market data
4. Search for "BTC funding rates open interest ETF flows today" for crypto derivatives color
5. Visit https://finance.yahoo.com/quote/MSTR/, https://finance.yahoo.com/quote/COIN/, https://finance.yahoo.com/quote/HOOD/, https://finance.yahoo.com/quote/NVDA/, https://finance.yahoo.com/quote/MARA/ for equity data
6. Search for "crypto market news today" for any breaking developments

After gathering data, write the brief. CITE EVERY DATA POINT with its source in brackets, e.g. [Yahoo Finance], [CoinGlass], [SoSoValue], [Deribit], etc. If a number is stale or unverified, say so.

Act as my institutional morning market-color analyst.
Audience: a professional trader at Paradigm.
Goal: dense, no-fluff morning brief. Prioritize signal over noise, positioning over headlines, catalysts over recap.

Timestamp the brief in ET and UTC. Separate facts from interpretation.

Crypto focus: BTC, ETH, SOL, majors, perp funding, spot/perp basis, options skew, ETF flows, stablecoin flows, OI, liquidations, exchange flows, unlocks, protocol developments.
Macro focus: US 2y, US 10y, real yields, DXY, USDJPY, CNH, gold, oil, VIX, SPX, NDX, credit spreads, central-bank expectations, economic data.
Equities: {equities}

OUTPUT STRUCTURE:

1) Top line
5-8 bullets. Each bullet: what happened [source], why it matters, regime-relevant or noise.

2) Cross-asset dashboard
Compact table: asset | level [source] | 24h move | 5d move | interpretation.
Include: BTC, ETH, SOL, BTC funding, BTC basis, DXY, US 2y, US 10y, SPX, NQ, VIX, gold, oil, USDJPY.
Flag statistically large moves vs recent realized.

3) Crypto color
- Price action and internals: spot vs perp-led, OI change, liquidations, funding, basis, options skew, ETF flows [cite source for each]
- Flow: stablecoin mint/burn, exchange flows, whale activity only if material [cite source]
- Sector: majors, L1s, DeFi, memecoins — only where volume/catalyst is real
- Idiosyncratic: listings, regulatory, governance, hacks, unlocks
End with: "What matters most for crypto today" — 3 bullets.

4) Macro color
- Overnight recap: Asia, Europe, US premarket [cite sources]
- Main macro driver
- What rates/FX/commodities are saying
- Session type: liquidity, growth scare, inflation scare, policy relief, squeeze, or idiosyncratic
- How macro feeds into crypto beta/vol/correlation

5) Equities of interest
For each ticker in {equities}: move [Yahoo Finance], driver, crypto relevance, catalysts, key levels.

6) Yahoo Finance headlines
Top 5-8 headlines from Yahoo Finance that matter for markets today. For each: headline, why it matters, and whether it affects crypto.

7) What changed since yesterday?
3-5 deltas that would change priors. Do not repeat stale narratives.

8) Calendar and catalysts next 24h
Exact times in ET. Rank by expected impact. Include: economic data, central-bank speakers, Treasury auctions, earnings, token unlocks, ETF decisions, regulatory deadlines, governance votes, major expiries.

9) Positioning and variant perception
What market believes, what is underpriced, consensus leans, what invalidates consensus.

10) Trade framing
Base/bull/bear case, levels and triggers, flow confirmation needed, cross-asset expressions or hedges. No forced ideas — only setups with catalyst, dislocation, or positioning edge.

11) Bottom line
Exactly three lines:
- The one thing that matters most today:
- What I'm watching first at the open:
- What would make me change my mind:

STYLE RULES:
- Concise, specific, skeptical, useful
- No basic explanations or generic recap language
- Numbers, levels, flows, catalysts over adjectives
- ALWAYS cite sources in [brackets] next to data points
- Say when something is noise
- Say when data is stale or unverified
- Keep the whole brief readable in 5 minutes
- Don't bury the lede

After writing the brief, post it to Slack channel "morning-brief" using the slack tool's send_message method. Format with emoji section headers for readability."""


async def handler(inp: Input, ctx: WorkflowContext) -> dict[str, Any]:
    """Run the morning market brief on a daily loop."""

    equities_str = ", ".join(inp.equities)
    prompt = BRIEF_PROMPT.format(equities=equities_str)
    iteration = 0

    while True:
        iteration += 1
        tz = ZoneInfo(inp.timezone)
        now = dt.datetime.now(dt.timezone.utc).astimezone(tz)

        # Skip weekends (Saturday=5, Sunday=6)
        next_run = now.replace(
            hour=inp.run_hour,
            minute=inp.run_minute,
            second=0,
            microsecond=0,
        )
        if next_run <= now:
            next_run += dt.timedelta(days=1)

        await ctx.sleep(f"wait_{iteration}", next_run - now)

        # Run the agent to gather data and produce the brief
        result = await ctx.run_agent(
            f"brief_{iteration}",
            text=prompt,
        )

        # Post to Slack if configured
        if inp.slack_channel and isinstance(result, dict):
            result_text = result.get("result_text", "")
            if result_text:
                date_str = dt.datetime.now(dt.timezone.utc).astimezone(tz).strftime("%Y-%m-%d")
                await ctx.run_agent(
                    f"post_slack_{iteration}",
                    text=(
                        f"Post the following morning market brief to the #{inp.slack_channel} "
                        f"Slack channel. Use the slack tool. Title it 'Morning Market Brief — {date_str}'.\n\n"
                        f"{result_text}"
                    ),
                )

        if inp.max_iterations > 0 and iteration >= inp.max_iterations:
            return {
                "status": "done",
                "iterations": iteration,
                "last_result": result,
            }
