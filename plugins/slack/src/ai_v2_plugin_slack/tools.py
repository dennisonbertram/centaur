"""Slack plugin tools — works both as imported plugin and standalone."""

from __future__ import annotations

import asyncio
import functools
import os
from typing import Any

from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

# --- Plugin registration (no-op if ai_v2 not installed) ---
try:
    from ai_v2.plugin_sdk import plugin_tool, secret
except ImportError:

    def plugin_tool(*, name: str | None = None):  # type: ignore[misc]
        def decorator(fn: Any) -> Any:
            fn.__plugin_tool__ = name or fn.__name__
            return fn
        return decorator

    def secret(key: str, default: str | None = None) -> str:  # type: ignore[misc]
        val = os.environ.get(key)
        if val:
            return val
        if default is not None:
            return default
        raise KeyError(f"Missing env var '{key}'")


def _client() -> WebClient:
    return WebClient(token=secret("SLACK_BOT_TOKEN"))


async def _in_thread(fn: Any, *args: Any, **kwargs: Any) -> Any:
    return await asyncio.get_event_loop().run_in_executor(
        None, functools.partial(fn, *args, **kwargs)
    )


@plugin_tool()
async def search_messages(
    query: str,
    channels: str = "",
    limit: int = 20,
) -> list[dict]:
    """Search Slack messages across all bot-accessible channels.

    Args:
        query: Text to search for (case-insensitive)
        channels: Comma-separated channel names to filter (optional)
        limit: Max results to return
    """
    client = _client()

    bot_channels = await _in_thread(
        client.conversations_list,
        types="public_channel,private_channel",
        limit=500,
        exclude_archived=True,
    )

    channel_list = [
        ch for ch in bot_channels.get("channels", []) if ch.get("is_member")
    ]

    if channels:
        filter_names = {c.strip().lstrip("#").lower() for c in channels.split(",")}
        channel_list = [ch for ch in channel_list if ch["name"].lower() in filter_names]

    query_terms = [t.lower() for t in query.split() if t.strip()]
    results: list[dict] = []

    for ch in channel_list:
        if len(results) >= limit:
            break
        try:
            history = await _in_thread(
                client.conversations_history,
                channel=ch["id"],
                limit=200,
            )
        except SlackApiError:
            continue

        for msg in history.get("messages", []):
            text = msg.get("text", "")
            if any(term in text.lower() for term in query_terms):
                ts = msg.get("ts", "")
                results.append({
                    "channel": ch["name"],
                    "user": msg.get("user", ""),
                    "text": text[:500],
                    "ts": ts,
                    "permalink": f"https://slack.com/archives/{ch['id']}/p{ts.replace('.', '')}",
                    "reply_count": msg.get("reply_count", 0),
                })
                if len(results) >= limit:
                    break

    return results


@plugin_tool()
async def channel_history(channel: str, limit: int = 50) -> list[dict]:
    """Get recent messages from a Slack channel.

    Args:
        channel: Channel name (without #) or channel ID
        limit: Number of messages to return
    """
    client = _client()

    channel_id = channel
    if not channel.startswith(("C", "G")):
        channels_resp = await _in_thread(
            client.conversations_list,
            types="public_channel,private_channel",
            limit=500,
            exclude_archived=True,
        )
        for ch in channels_resp.get("channels", []):
            if ch["name"] == channel.lstrip("#"):
                channel_id = ch["id"]
                break
        else:
            return [{"error": f"Channel '{channel}' not found"}]

    history = await _in_thread(
        client.conversations_history,
        channel=channel_id,
        limit=limit,
    )

    messages = []
    for msg in history.get("messages", []):
        ts = msg.get("ts", "")
        messages.append({
            "user": msg.get("user", ""),
            "text": msg.get("text", "")[:500],
            "ts": ts,
            "permalink": f"https://slack.com/archives/{channel_id}/p{ts.replace('.', '')}",
            "reply_count": msg.get("reply_count", 0),
            "thread_ts": msg.get("thread_ts"),
        })
    return messages


@plugin_tool()
async def thread(channel_id: str, thread_ts: str) -> list[dict]:
    """Get all replies in a Slack thread.

    Args:
        channel_id: Channel ID (e.g. C01234567)
        thread_ts: Thread timestamp
    """
    client = _client()

    replies = await _in_thread(
        client.conversations_replies,
        channel=channel_id,
        ts=thread_ts,
        limit=200,
        inclusive=True,
    )

    return [
        {
            "user": msg.get("user", ""),
            "text": msg.get("text", "")[:500],
            "ts": msg.get("ts", ""),
        }
        for msg in replies.get("messages", [])
    ]


@plugin_tool()
async def list_channels(include_private: bool = True) -> list[dict]:
    """List Slack channels the bot has access to."""
    client = _client()

    types = "public_channel,private_channel" if include_private else "public_channel"
    resp = await _in_thread(
        client.conversations_list,
        types=types,
        limit=500,
        exclude_archived=True,
    )

    return [
        {
            "id": ch["id"],
            "name": ch["name"],
            "is_private": ch.get("is_private", False),
            "member_count": ch.get("num_members", 0),
            "is_member": ch.get("is_member", False),
        }
        for ch in sorted(resp.get("channels", []), key=lambda c: c["name"])
    ]


@plugin_tool()
async def list_users(limit: int = 200) -> list[dict]:
    """List Slack workspace members."""
    client = _client()

    resp = await _in_thread(client.users_list, limit=limit)

    return [
        {
            "id": u["id"],
            "name": u.get("name", ""),
            "real_name": u.get("real_name", ""),
            "email": u.get("profile", {}).get("email", ""),
            "is_bot": u.get("is_bot", False),
        }
        for u in resp.get("members", [])
        if not u.get("deleted")
    ]
