"""Slack API client - bot token only (no user token required)."""

import os
import re
from concurrent.futures import ThreadPoolExecutor, as_completed

from dotenv import load_dotenv
from slack_sdk import WebClient
from slack_sdk.errors import SlackApiError

load_dotenv()


def get_slack_client() -> WebClient:
    """Get authenticated Slack client with bot token."""
    token = os.getenv("SLACK_BOT_TOKEN")
    if not token:
        raise RuntimeError(
            "SLACK_BOT_TOKEN not set. Add it to your .env file.\n"
            "Get one at https://api.slack.com/apps → OAuth & Permissions → Bot User OAuth Token"
        )
    return WebClient(token=token)


def resolve_mentions(text: str, client: WebClient, user_cache: dict[str, str]) -> str:
    """Replace <@USER_ID> mentions with @username."""

    def replace_mention(match: re.Match) -> str:
        user_id = match.group(1)
        if user_id in user_cache:
            return f"@{user_cache[user_id]}"
        try:
            info = client.users_info(user=user_id)
            name = info.get("user", {}).get("name", user_id)
            user_cache[user_id] = name
            return f"@{name}"
        except SlackApiError:
            user_cache[user_id] = user_id
            return f"@{user_id}"

    return re.sub(r"<@([A-Z0-9]+)>", replace_mention, text)


def list_bot_channels(include_private: bool = True, limit: int = 500) -> list[dict]:
    """List channels the bot is a member of.

    Args:
        include_private: Include private channels
        limit: Maximum channels to return

    Returns:
        List of channel dicts with id, name, is_private
    """
    client = get_slack_client()
    channels = []
    cursor = None
    types = "public_channel,private_channel" if include_private else "public_channel"

    while True:
        try:
            response = client.conversations_list(
                types=types,
                limit=min(limit - len(channels), 200),
                cursor=cursor,
                exclude_archived=True,
            )
        except SlackApiError as e:
            raise RuntimeError(f"Slack API error: {e.response['error']}")

        for channel in response.get("channels", []):
            if channel.get("is_member", False):
                channels.append(
                    {
                        "id": channel.get("id", ""),
                        "name": channel.get("name", ""),
                        "purpose": channel.get("purpose", {}).get("value", ""),
                        "topic": channel.get("topic", {}).get("value", ""),
                        "member_count": channel.get("num_members", 0),
                        "is_private": channel.get("is_private", False),
                    }
                )

        cursor = response.get("response_metadata", {}).get("next_cursor")
        if not cursor or len(channels) >= limit:
            break

    return sorted(channels, key=lambda x: x["name"])


def _fetch_channel_history(
    client: WebClient,
    channel_id: str,
    channel_name: str,
    limit: int,
    user_cache: dict[str, str],
) -> list[dict]:
    """Fetch history for a single channel (used by search)."""
    try:
        response = client.conversations_history(channel=channel_id, limit=limit)
    except SlackApiError:
        return []

    messages = []
    for msg in response.get("messages", []):
        user_id = msg.get("user", "")
        username = user_cache.get(user_id, user_id)
        text = msg.get("text", "")
        ts = msg.get("ts", "")

        messages.append(
            {
                "channel": channel_name,
                "channel_id": channel_id,
                "user": username,
                "user_id": user_id,
                "text": text,
                "timestamp": ts,
                "permalink": (
                    f"https://paradigm-ops.slack.com/archives/{channel_id}/p{ts.replace('.', '')}"
                ),
                "thread_ts": msg.get("thread_ts"),
                "reply_count": msg.get("reply_count", 0),
            }
        )

    return messages


def search_messages(
    query: str,
    max_results: int = 20,
    messages_per_channel: int = 100,
) -> list[dict]:
    """Search messages across bot-accessible channels using local filtering.

    Args:
        query: Text to search for (case-insensitive)
        max_results: Maximum results to return
        messages_per_channel: Messages to fetch per channel for searching

    Returns:
        List of matching message dicts
    """
    client = get_slack_client()

    bot_channels = list_bot_channels()
    if not bot_channels:
        return []

    user_cache: dict[str, str] = {}
    try:
        users_response = client.users_list(limit=500)
        for user in users_response.get("members", []):
            user_cache[user.get("id", "")] = user.get("name", "")
    except SlackApiError:
        pass

    all_messages = []
    with ThreadPoolExecutor(max_workers=10) as executor:
        futures = {
            executor.submit(
                _fetch_channel_history,
                client,
                ch["id"],
                ch["name"],
                messages_per_channel,
                user_cache,
            ): ch
            for ch in bot_channels
        }

        for future in as_completed(futures):
            try:
                messages = future.result()
                all_messages.extend(messages)
            except Exception:
                pass

    query_lower = query.lower()
    results = []

    for msg in all_messages:
        text_lower = msg["text"].lower()

        if query_lower not in text_lower:
            continue

        msg["user"] = user_cache.get(msg["user_id"], msg["user_id"])
        msg["text"] = resolve_mentions(msg["text"], client, user_cache)
        results.append(msg)

        if len(results) >= max_results:
            break

    results.sort(key=lambda x: x["timestamp"], reverse=True)
    return results[:max_results]


def get_message_context(channel_id: str, message_ts: str, context_count: int = 3) -> list[dict]:
    """Get messages around a specific message for context.

    Args:
        channel_id: The channel ID
        message_ts: The timestamp of the target message
        context_count: Number of messages before/after to fetch

    Returns:
        List of surrounding messages
    """
    client = get_slack_client()

    try:
        response = client.conversations_replies(
            channel=channel_id,
            ts=message_ts,
            limit=context_count * 2 + 1,
            inclusive=True,
        )
    except SlackApiError:
        return []

    messages = []
    for msg in response.get("messages", []):
        messages.append(
            {
                "user": msg.get("user", ""),
                "text": msg.get("text", ""),
                "timestamp": msg.get("ts", ""),
            }
        )

    return messages


def get_thread_replies(channel_id: str, thread_ts: str, limit: int = 100) -> list[dict]:
    """Get all replies in a thread.

    Args:
        channel_id: The channel ID
        thread_ts: The timestamp of the parent message
        limit: Maximum replies to fetch

    Returns:
        List of message dicts with user, text, timestamp
    """
    client = get_slack_client()
    user_cache: dict[str, str] = {}

    def get_username(user_id: str) -> str:
        if user_id in user_cache:
            return user_cache[user_id]
        try:
            info = client.users_info(user=user_id)
            name = info.get("user", {}).get("name", user_id)
            user_cache[user_id] = name
            return name
        except SlackApiError:
            return user_id

    try:
        response = client.conversations_replies(
            channel=channel_id,
            ts=thread_ts,
            limit=limit,
            inclusive=True,
        )
    except SlackApiError as e:
        raise RuntimeError(f"Slack API error: {e.response['error']}")

    messages = []
    for msg in response.get("messages", []):
        user_id = msg.get("user", "")
        messages.append(
            {
                "user": get_username(user_id),
                "text": msg.get("text", ""),
                "timestamp": msg.get("ts", ""),
            }
        )

    return messages


def list_channels(include_private: bool = False, limit: int = 200) -> list[dict]:
    """List all Slack channels with metadata.

    Args:
        include_private: Include private channels (requires membership)
        limit: Maximum number of channels to return

    Returns:
        List of channel dicts with id, name, purpose, member_count, is_private
    """
    client = get_slack_client()

    channels = []
    cursor = None
    types = "public_channel,private_channel" if include_private else "public_channel"

    while True:
        try:
            response = client.conversations_list(
                types=types,
                limit=min(limit - len(channels), 200),
                cursor=cursor,
                exclude_archived=True,
            )
        except SlackApiError as e:
            raise RuntimeError(f"Slack API error: {e.response['error']}")

        for channel in response.get("channels", []):
            channels.append(
                {
                    "id": channel.get("id", ""),
                    "name": channel.get("name", ""),
                    "purpose": channel.get("purpose", {}).get("value", ""),
                    "topic": channel.get("topic", {}).get("value", ""),
                    "member_count": channel.get("num_members", 0),
                    "is_private": channel.get("is_private", False),
                }
            )

        cursor = response.get("response_metadata", {}).get("next_cursor")
        if not cursor or len(channels) >= limit:
            break

    return sorted(channels, key=lambda x: x["name"])


def get_channel_history(channel: str, limit: int = 50) -> list[dict]:
    """Get recent messages from a channel.

    Args:
        channel: Channel name (without #) or channel ID
        limit: Maximum number of messages to return

    Returns:
        List of message dicts with user, text, timestamp, permalink
    """
    client = get_slack_client()
    user_cache: dict[str, str] = {}

    def get_username(user_id: str) -> str:
        if not user_id:
            return "unknown"
        if user_id in user_cache:
            return user_cache[user_id]
        try:
            info = client.users_info(user=user_id)
            name = info.get("user", {}).get("name", user_id)
            user_cache[user_id] = name
            return name
        except SlackApiError:
            user_cache[user_id] = user_id
            return user_id

    # Resolve channel name to ID if needed
    channel_id = channel
    if not channel.startswith("C") and not channel.startswith("G"):
        channels = list_bot_channels(include_private=True, limit=1000)
        for ch in channels:
            if ch["name"] == channel or ch["name"] == channel.lstrip("#"):
                channel_id = ch["id"]
                break
        else:
            raise RuntimeError(f"Channel '{channel}' not found or bot not a member")

    try:
        response = client.conversations_history(channel=channel_id, limit=limit)
    except SlackApiError as e:
        raise RuntimeError(f"Slack API error: {e.response['error']}")

    messages = []
    for msg in response.get("messages", []):
        user_id = msg.get("user", "")
        ts = msg.get("ts", "")

        # Build permalink
        permalink = f"https://paradigm-ops.slack.com/archives/{channel_id}/p{ts.replace('.', '')}"

        messages.append(
            {
                "user": get_username(user_id),
                "text": msg.get("text", ""),
                "timestamp": ts,
                "permalink": permalink,
                "channel_id": channel_id,
                "thread_ts": msg.get("thread_ts"),
                "reply_count": msg.get("reply_count", 0),
            }
        )

    # Reverse to show oldest first (API returns newest first)
    return list(reversed(messages))


def list_users(limit: int = 500) -> list[dict]:
    """List all Slack workspace members with metadata.

    Args:
        limit: Maximum number of users to return

    Returns:
        List of user dicts with id, name, real_name, email, title, is_bot
    """
    client = get_slack_client()

    users = []
    cursor = None

    while True:
        try:
            response = client.users_list(
                limit=min(limit - len(users), 200),
                cursor=cursor,
            )
        except SlackApiError as e:
            raise RuntimeError(f"Slack API error: {e.response['error']}")

        for user in response.get("members", []):
            if user.get("deleted"):
                continue

            profile = user.get("profile", {})
            users.append(
                {
                    "id": user.get("id", ""),
                    "name": user.get("name", ""),
                    "real_name": profile.get("real_name", ""),
                    "email": profile.get("email", ""),
                    "title": profile.get("title", ""),
                    "is_bot": user.get("is_bot", False),
                }
            )

        cursor = response.get("response_metadata", {}).get("next_cursor")
        if not cursor or len(users) >= limit:
            break

    return sorted(users, key=lambda x: x["real_name"] or x["name"])


def get_user_id_by_email(email: str) -> str | None:
    """Get Slack user ID by email address."""
    client = get_slack_client()
    try:
        response = client.users_lookupByEmail(email=email)
        return response.get("user", {}).get("id")
    except SlackApiError:
        return None


def open_conversation(user_ids: list[str]) -> str:
    """Open a direct message or group DM with users.

    Args:
        user_ids: List of Slack user IDs

    Returns:
        Channel ID for the conversation
    """
    client = get_slack_client()
    try:
        response = client.conversations_open(users=user_ids)
        return response.get("channel", {}).get("id", "")
    except SlackApiError as e:
        raise RuntimeError(f"Slack API error: {e.response['error']}")


def send_message(channel: str, text: str, thread_ts: str | None = None) -> dict:
    """Send a message to a channel or DM.

    Args:
        channel: Channel ID or conversation ID
        text: Message text (supports Slack mrkdwn)
        thread_ts: Optional thread timestamp to reply to

    Returns:
        Dict with ts, channel, permalink
    """
    client = get_slack_client()
    try:
        kwargs = {"channel": channel, "text": text}
        if thread_ts:
            kwargs["thread_ts"] = thread_ts
        response = client.chat_postMessage(**kwargs)
        return {
            "ts": response.get("ts", ""),
            "channel": response.get("channel", ""),
            "ok": response.get("ok", False),
        }
    except SlackApiError as e:
        raise RuntimeError(f"Slack API error: {e.response['error']}")
