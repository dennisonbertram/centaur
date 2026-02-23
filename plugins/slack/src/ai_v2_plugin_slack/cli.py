"""Slack plugin CLI — standalone usage for debugging/testing."""

from __future__ import annotations

import asyncio
import json

import typer
from dotenv import load_dotenv

from . import tools

load_dotenv()

app = typer.Typer(help="Slack plugin CLI")


def _run(coro):
    """Print result of an async tool call as JSON."""
    result = asyncio.run(coro)
    typer.echo(json.dumps(result, indent=2, default=str))


@app.command()
def search(
    query: str,
    channels: str = typer.Option("", help="Comma-separated channel names"),
    limit: int = typer.Option(20, help="Max results"),
):
    """Search Slack messages."""
    _run(tools.search_messages(query, channels=channels, limit=limit))


@app.command()
def channel(
    name: str,
    limit: int = typer.Option(50, "-n", help="Number of messages"),
):
    """Get recent messages from a channel."""
    _run(tools.channel_history(name, limit=limit))


@app.command("thread")
def get_thread(
    channel_id: str,
    thread_ts: str,
):
    """Get all replies in a thread."""
    _run(tools.thread(channel_id, thread_ts))


@app.command("channels")
def channels_cmd(
    include_private: bool = typer.Option(True, help="Include private channels"),
):
    """List channels."""
    _run(tools.list_channels(include_private=include_private))


@app.command("users")
def users_cmd(
    limit: int = typer.Option(200, help="Max users"),
):
    """List workspace members."""
    _run(tools.list_users(limit=limit))
