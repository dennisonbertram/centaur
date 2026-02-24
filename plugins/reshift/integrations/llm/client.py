"""Amp CLI integration for natural language queries."""

import json
import logging
import os
import subprocess
from collections.abc import Callable

logger = logging.getLogger("reshift.llm")

AMP_PATH = os.path.expanduser("~/.amp/bin/amp")
WORKSPACE = os.path.expanduser("~/github/paradigmxyz/reshift")

SLACK_FORMAT_INSTRUCTIONS = """Format your response for Slack:
- Use *bold* for emphasis (not **markdown**)
- Use _italic_ for subtle emphasis  
- Use bullet points with • or -
- Keep responses concise (under 2000 chars if possible)
- For calendar/list data, format like:
  • *10:00* - Meeting name (attendees)
  • *14:00* - Another event

Answer this question:"""


def ask(question: str, timeout: int = 120) -> str:
    """Run a query through Amp and return the response.

    Args:
        question: The natural language question to answer
        timeout: Maximum seconds to wait for response

    Returns:
        The Amp agent's response text
    """
    result, _, _ = ask_with_progress(question, timeout=timeout)
    return result


def ask_with_progress(
    question: str,
    on_progress: Callable[[str], None] | None = None,
    on_session_start: Callable[[str], None] | None = None,
    continue_thread_id: str | None = None,
    timeout: int = 120,
) -> tuple[str, list[dict], str | None]:
    """Run a query through Amp with progress callbacks.

    Args:
        question: The natural language question to answer
        on_progress: Callback for progress updates (tool uses, etc.)
        on_session_start: Callback when session starts, receives thread ID
        continue_thread_id: If provided, continue this existing Amp thread
        timeout: Maximum seconds to wait for response

    Returns:
        Tuple of (final response, list of events, thread_id)
    """
    events = []
    final_response = ""
    thread_id = continue_thread_id  # Start with existing thread if continuing

    # Prepend Slack formatting instructions
    formatted_question = f"{SLACK_FORMAT_INSTRUCTIONS}\n{question}"

    # Build command - either continue existing thread or start new
    if continue_thread_id:
        logger.debug(f"Continuing Amp thread {continue_thread_id}")
        cmd = [
            AMP_PATH,
            "threads",
            "continue",
            continue_thread_id,
            "--no-ide",
            "--no-notifications",
            "--dangerously-allow-all",
            "-x",
            formatted_question,
            "--stream-json",
        ]
    else:
        logger.debug(f"Starting new Amp thread with question length: {len(formatted_question)}")
        cmd = [
            AMP_PATH,
            "--no-ide",
            "--no-notifications",
            "--dangerously-allow-all",
            "-x",
            formatted_question,
            "--stream-json",
        ]

    try:
        process = subprocess.Popen(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
            cwd=WORKSPACE,
        )
        logger.debug(f"Amp process started: pid={process.pid}")

        for line in process.stdout:
            line = line.strip()
            if not line:
                continue

            try:
                event = json.loads(line)
                events.append(event)

                # Capture thread ID from init event
                if event.get("type") == "system" and event.get("subtype") == "init":
                    thread_id = event.get("session_id")
                    logger.info(f"Amp session started: thread_id={thread_id}")
                    if on_session_start and thread_id:
                        on_session_start(thread_id)

                # Extract progress info for callback
                if on_progress:
                    progress_msg = _extract_progress(event)
                    if progress_msg:
                        logger.debug(f"Progress: {progress_msg}")
                        on_progress(progress_msg)

                # Capture final result
                if event.get("type") == "result":
                    final_response = event.get("result", "")
                    logger.debug(f"Got result: {len(final_response)} chars")

            except json.JSONDecodeError:
                logger.warning(f"Failed to parse JSON line: {line[:100]}")
                continue

        process.wait(timeout=timeout)
        logger.debug(f"Amp process exited: returncode={process.returncode}")

        if not final_response:
            logger.warning("No response from Amp")
            return "No response from Amp", events, thread_id

        return final_response, events, thread_id

    except subprocess.TimeoutExpired:
        logger.error(f"Amp process timed out after {timeout}s")
        process.kill()
        return "Request timed out (exceeded 2 minutes)", events, thread_id
    except FileNotFoundError:
        logger.error(f"Amp CLI not found at {AMP_PATH}")
        return "Amp CLI not found. Is it installed?", events, None
    except Exception as e:
        logger.exception(f"Error running Amp: {e}")
        return f"Error running Amp: {e}", events, thread_id


def _extract_progress(event: dict) -> str | None:
    """Extract a human-readable progress message from an Amp event."""
    event_type = event.get("type")

    if event_type == "system" and event.get("subtype") == "init":
        return "🚀 Starting Amp session..."

    if event_type == "assistant":
        msg = event.get("message", {})
        content = msg.get("content", [])

        for block in content:
            # Tool use - show what tool is being called
            if block.get("type") == "tool_use":
                tool_name = block.get("name", "unknown")
                tool_input = block.get("input", {})

                # Format tool-specific messages
                if tool_name == "Bash":
                    cmd = tool_input.get("cmd", "")[:80]
                    return f"⚡ Running: `{cmd}`"
                elif tool_name == "Read":
                    path = tool_input.get("path", "").split("/")[-1]
                    return f"📖 Reading: {path}"
                elif tool_name == "Grep":
                    pattern = tool_input.get("pattern", "")
                    return f"🔍 Searching: `{pattern}`"
                elif tool_name == "finder":
                    query = tool_input.get("query", "")[:60]
                    return f"🔎 Finding: {query}"
                elif tool_name == "web_search":
                    return "🌐 Searching web..."
                elif tool_name == "read_web_page":
                    url = tool_input.get("url", "")
                    return f"📄 Reading: {url[:50]}..."
                else:
                    return f"🔧 Using: {tool_name}"

    return None
