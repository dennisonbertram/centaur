"""GSuite plugin tools — works both as imported plugin and standalone."""

from __future__ import annotations

import asyncio
import functools
import os
from typing import Any

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


from .client import (
    gmail_search as _gmail_search,
    gmail_read as _gmail_read,
    gmail_send as _gmail_send,
    calendar_list as _calendar_list,
    calendar_events as _calendar_events,
    calendar_create_event as _calendar_create_event,
    drive_get as _drive_get,
    drive_list as _drive_list,
)


async def _in_thread(fn: Any, *args: Any, **kwargs: Any) -> Any:
    return await asyncio.get_event_loop().run_in_executor(
        None, functools.partial(fn, *args, **kwargs)
    )


# --- Gmail ---


@plugin_tool()
async def gmail_search(query: str, max_results: int = 20) -> list[dict]:
    """Search Gmail messages.

    Args:
        query: Gmail search query (same syntax as Gmail web)
        max_results: Maximum number of results
    """
    return await _in_thread(_gmail_search, query, max_results=max_results)


@plugin_tool()
async def gmail_get(message_id: str) -> dict:
    """Read a specific Gmail message by ID.

    Args:
        message_id: The message ID
    """
    return await _in_thread(_gmail_read, message_id)


@plugin_tool()
async def gmail_send(
    to: str, subject: str, body: str, cc: str | None = None
) -> dict:
    """Send an email.

    Args:
        to: Recipient email address
        subject: Email subject
        body: Email body (plain text)
        cc: Optional CC recipients
    """
    return await _in_thread(_gmail_send, to, subject, body, cc=cc)


# --- Calendar ---


@plugin_tool()
async def calendar_list() -> list[dict]:
    """List all calendars."""
    return await _in_thread(_calendar_list)


@plugin_tool()
async def calendar_events(
    calendar_id: str = "primary",
    time_min: str | None = None,
    time_max: str | None = None,
    max_results: int = 50,
    query: str | None = None,
) -> list[dict]:
    """List calendar events.

    Args:
        calendar_id: Calendar ID (default: primary)
        time_min: Start time in RFC3339 format
        time_max: End time in RFC3339 format
        max_results: Maximum number of events
        query: Search query
    """
    return await _in_thread(
        _calendar_events,
        calendar_id=calendar_id,
        time_min=time_min,
        time_max=time_max,
        max_results=max_results,
        query=query,
    )


@plugin_tool()
async def calendar_create_event(
    summary: str,
    start: str,
    end: str,
    calendar_id: str = "primary",
    description: str | None = None,
    location: str | None = None,
    attendees: list[str] | None = None,
) -> dict:
    """Create a calendar event.

    Args:
        summary: Event title
        start: Start time in RFC3339 format or date (YYYY-MM-DD)
        end: End time in RFC3339 format or date
        calendar_id: Calendar ID (default: primary)
        description: Event description
        location: Event location
        attendees: List of attendee emails
    """
    return await _in_thread(
        _calendar_create_event,
        summary,
        start,
        end,
        calendar_id=calendar_id,
        description=description,
        location=location,
        attendees=attendees,
    )


# --- Drive ---


@plugin_tool()
async def drive_search(query: str, max_results: int = 50) -> list[dict]:
    """Search files in Google Drive by name.

    Args:
        query: Search query (matches file names)
        max_results: Maximum number of results
    """
    return await _in_thread(_drive_list, query=query, max_results=max_results)


@plugin_tool()
async def drive_get(file_id: str) -> dict:
    """Get file metadata from Google Drive.

    Args:
        file_id: The file ID
    """
    return await _in_thread(_drive_get, file_id)


@plugin_tool()
async def drive_list(
    folder_id: str | None = None,
    max_results: int = 50,
    file_type: str | None = None,
) -> list[dict]:
    """List files in Google Drive.

    Args:
        folder_id: Folder ID to list contents
        max_results: Maximum number of results
        file_type: Filter by MIME type prefix
    """
    return await _in_thread(
        _drive_list,
        folder_id=folder_id,
        max_results=max_results,
        file_type=file_type,
    )
