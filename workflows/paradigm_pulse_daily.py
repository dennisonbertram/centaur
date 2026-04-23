"""Workflow: daily Paradigm Pulse digest.

Posts to #paradigm-pulse every morning at 7:45am PT.
"""

from __future__ import annotations

import re
from urllib.parse import urlparse

WORKFLOW_NAME = "paradigm_pulse_daily"
CRON = "45 7 * * *"
SLACK_CHANNEL = "paradigm-pulse"

PROMPT = (
    "Generate today's Paradigm Pulse digest for Paradigm I&R and "
    "Marketing. Use Centaur tools to gather fresh signals across "
    "Paradigm mentions, Paradigm team activity, portfolio company "
    "momentum, relevant market/news signals, and notable "
    "influential-circle content.\n\n"
    "Output concise Slack-native mrkdwn using only these section "
    "headings when there is signal, with each heading on its own bold "
    "line exactly as written below:\n"
    "- News\n"
    "- Trending on X\n"
    "- Paradigm team on X\n"
    "- Portfolio\n"
    "- Influential Circles on X\n\n"
    "Avoid low-signal filler. Reuse the existing thread context to "
    "avoid repeating items that were already posted recently unless "
    "they changed materially. Use Slack links inline as `<url|label>`; "
    "do not emit bare URLs or GitHub-style markdown links `[text](url)`."
)

_MARKDOWN_LINK_RE = re.compile(r"\[([^\]]+)\]\((https?://[^)\s]+)\)")
_RAW_URL_RE = re.compile(r"(?<!<)https?://[^\s>]+")


def _clip_label(text: str, max_chars: int = 32) -> str:
    clipped = text.strip()
    if len(clipped) <= max_chars:
        return clipped
    return clipped[: max_chars - 1].rstrip("/-_") + "..."


def _default_link_label(url: str) -> str:
    parsed = urlparse(url)
    host = parsed.netloc.lower().removeprefix("www.")
    segments = [segment for segment in parsed.path.split("/") if segment]
    if host in {"x.com", "twitter.com"} and segments:
        return f"@{segments[0]}"
    if not segments:
        return host or "link"
    slug = segments[-1]
    if slug.isdigit() and len(segments) >= 2:
        slug = segments[-2]
    return _clip_label(f"{host}/{slug}" if host else slug)


def _slackify_links(text: str) -> str:
    if not text:
        return ""

    slackified = _MARKDOWN_LINK_RE.sub(
        lambda match: f"<{match.group(2)}|{match.group(1).strip()}>",
        text,
    )

    def _replace_raw_url(match: re.Match[str]) -> str:
        raw = match.group(0)
        url = raw.rstrip(".,;:!?)")
        suffix = raw[len(url):]
        return f"<{url}|{_default_link_label(url)}>{suffix}"

    return _RAW_URL_RE.sub(_replace_raw_url, slackified)


async def handler(inp, ctx):
    result = await ctx.agent_turn(PROMPT)
    formatted_text = _slackify_links(str(result.get("result_text") or "").strip())
    channel = (inp.get("slack_channel") if isinstance(inp, dict) else None) or SLACK_CHANNEL
    if formatted_text and channel:
        await ctx.post_to_slack(channel, formatted_text)

    normalized_result = dict(result)
    normalized_result["result_text"] = formatted_text
    execution = normalized_result.get("execution")
    if isinstance(execution, dict):
        normalized_execution = dict(execution)
        normalized_execution["result_text"] = formatted_text
        normalized_result["execution"] = normalized_execution
    return normalized_result
