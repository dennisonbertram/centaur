"""Workflow: recurring personal daily checklist digest.

Collects the latest prior-day checklist section from a Google Doc tab,
current-week Granola notes owned by the user, and recent Slack threads that
mention the user. It then asks the agent to turn that source material
into a copy-paste-ready checklist for Slack/Google Docs.
"""

from __future__ import annotations

import datetime as dt
import json
import re
from dataclasses import dataclass, field
from typing import Any
from urllib.parse import parse_qs, urlparse
from zoneinfo import ZoneInfo

from api.runtime_control import ControlPlaneError
from api.workflow_engine import Delivery, WorkflowContext

WORKFLOW_NAME = "daily_checklist_digest"

_DATE_FORMATS = ("%b %d, %Y", "%B %d, %Y")
_DATE_LINE_RE = re.compile(r"^(?:[A-Z][a-z]{2,8})\s+\d{1,2},\s+\d{4}$")
_GOOGLE_DOC_ID_RE = re.compile(r"/document/d/([a-zA-Z0-9_-]+)")
_CONTROL_CHAR_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")


@dataclass
class Input:
    document_id: str = ""
    document_url: str = ""
    doc_tab_id: str = ""
    doc_tab_title: str = "Daily Standup"
    slack_channel: str = ""
    slack_thread_ts: str = ""
    slack_user_id: str = ""
    slack_user_name: str = ""
    slack_search_terms: list[str] = field(default_factory=list)
    granola_owner_email: str = ""
    timezone: str = "America/New_York"
    run_hour: int = 8
    run_minute: int = 0
    max_slack_threads: int = 8
    max_thread_replies: int = 6
    max_granola_notes: int = 5
    send_immediately: bool = True
    max_iterations: int = 0
    thread_key: str = ""
    delivery: Delivery = field(default_factory=Delivery)
    metadata: dict[str, Any] = field(default_factory=dict)


def _resolve_document_id(inp: Input) -> str:
    if inp.document_id.strip():
        return inp.document_id.strip()

    if not inp.document_url.strip():
        raise ControlPlaneError(
            "INVALID_WORKFLOW_INPUT",
            "daily_checklist_digest requires document_id or document_url",
            422,
        )

    parsed = urlparse(inp.document_url.strip())
    match = _GOOGLE_DOC_ID_RE.search(parsed.path)
    if not match:
        raise ControlPlaneError(
            "INVALID_WORKFLOW_INPUT",
            f"could not extract Google Doc ID from: {inp.document_url}",
            422,
        )
    return match.group(1)


def _resolve_tab_id(inp: Input) -> str:
    if inp.doc_tab_id.strip():
        return inp.doc_tab_id.strip()

    if not inp.document_url.strip():
        return ""

    query = parse_qs(urlparse(inp.document_url.strip()).query)
    tab_values = query.get("tab") or []
    return tab_values[0].strip() if tab_values else ""


def _normalize_text(value: str) -> str:
    cleaned = _CONTROL_CHAR_RE.sub(" ", value.replace("\r", "\n"))
    cleaned = re.sub(r"\n{3,}", "\n\n", cleaned)
    return cleaned.strip()


def _extract_doc_text_from_content(content: list[dict[str, Any]]) -> str:
    parts: list[str] = []

    for block in content:
        paragraph = block.get("paragraph")
        if paragraph:
            for element in paragraph.get("elements", []):
                text_run = element.get("textRun")
                if text_run:
                    parts.append(text_run.get("content", ""))
                    continue

                date_element = element.get("dateElement")
                if date_element:
                    props = date_element.get("dateElementProperties", {})
                    parts.append(props.get("displayText") or "")
            continue

        table = block.get("table")
        if table:
            for row in table.get("tableRows", []):
                for cell in row.get("tableCells", []):
                    cell_text = _extract_doc_text_from_content(cell.get("content", []))
                    if cell_text:
                        parts.append(cell_text)
            continue

        table_of_contents = block.get("tableOfContents")
        if table_of_contents:
            toc_text = _extract_doc_text_from_content(table_of_contents.get("content", []))
            if toc_text:
                parts.append(toc_text)

    return _normalize_text("".join(parts))


def _extract_tab_text(document: dict[str, Any], *, tab_id: str, tab_title: str) -> str:
    for tab in document.get("tabs", []):
        props = tab.get("tabProperties", {})
        if tab_id and props.get("tabId") != tab_id:
            continue
        if tab_title and props.get("title") != tab_title and not tab_id:
            continue

        document_tab = tab.get("documentTab") or {}
        body = document_tab.get("body") or {}
        return _extract_doc_text_from_content(body.get("content", []))

    raise ControlPlaneError(
        "INVALID_WORKFLOW_INPUT",
        f"could not find tab '{tab_title or tab_id}' in document",
        422,
    )


def _parse_date_line(line: str) -> dt.date | None:
    text = line.strip()
    if not _DATE_LINE_RE.match(text):
        return None

    for fmt in _DATE_FORMATS:
        try:
            return dt.datetime.strptime(text, fmt).date()
        except ValueError:
            continue
    return None


def _extract_dated_sections(text: str) -> list[tuple[dt.date, str]]:
    sections: list[tuple[dt.date, str]] = []
    current_date: dt.date | None = None
    current_lines: list[str] = []

    for raw_line in text.splitlines():
        line = raw_line.strip()
        if not line:
            if current_lines and current_lines[-1] != "":
                current_lines.append("")
            continue

        section_date = _parse_date_line(line)
        if section_date is not None:
            if current_date is not None:
                section_text = "\n".join(current_lines).strip()
                if section_text:
                    sections.append((current_date, section_text))
            current_date = section_date
            current_lines = []
            continue

        if current_date is not None:
            current_lines.append(line)

    if current_date is not None:
        section_text = "\n".join(current_lines).strip()
        if section_text:
            sections.append((current_date, section_text))

    return sections


def _select_previous_section(
    text: str,
    *,
    today: dt.date,
) -> tuple[dt.date | None, str]:
    sections = _extract_dated_sections(text)
    if not sections:
        return None, text.strip()

    prior_sections = [
        (section_date, section_text)
        for section_date, section_text in sections
        if section_date < today
    ]
    if prior_sections:
        return max(prior_sections, key=lambda section: section[0])
    return max(sections, key=lambda section: section[0])


def _start_of_previous_day_utc(now_local: dt.datetime) -> tuple[dt.date, dt.datetime]:
    previous_day = now_local.date() - dt.timedelta(days=1)
    local_start = dt.datetime.combine(previous_day, dt.time.min, tzinfo=now_local.tzinfo)
    return previous_day, local_start.astimezone(dt.timezone.utc)


def _start_of_week_utc(now_local: dt.datetime) -> tuple[dt.date, dt.datetime]:
    week_start = now_local.date() - dt.timedelta(days=now_local.weekday())
    local_start = dt.datetime.combine(week_start, dt.time.min, tzinfo=now_local.tzinfo)
    return week_start, local_start.astimezone(dt.timezone.utc)


def _next_run_delta(
    now_local: dt.datetime,
    *,
    run_hour: int,
    run_minute: int,
) -> dt.timedelta:
    next_run = now_local.replace(
        hour=run_hour,
        minute=run_minute,
        second=0,
        microsecond=0,
    )
    if next_run <= now_local:
        next_run += dt.timedelta(days=1)
    return next_run - now_local


def _unique_search_terms(inp: Input) -> list[str]:
    terms: list[str] = []
    seen: set[str] = set()

    def add(term: str) -> None:
        normalized = term.strip()
        if not normalized:
            return
        key = normalized.casefold()
        if key in seen:
            return
        seen.add(key)
        terms.append(normalized)

    for term in inp.slack_search_terms:
        add(term)

    add(inp.slack_user_name)
    if inp.slack_user_name.strip():
        add(inp.slack_user_name.strip().split()[0])

    return terms


def _slack_query_for_term(term: str, previous_day: dt.date) -> str:
    rendered_term = f'"{term}"' if " " in term else term
    return f"{rendered_term} after:{previous_day.isoformat()}"


def _truncate_utterances(utterances: list[str], limit: int = 6) -> list[str]:
    trimmed: list[str] = []
    for utterance in utterances:
        cleaned = _normalize_text(utterance)
        if not cleaned:
            continue
        if len(cleaned) > 280:
            cleaned = f"{cleaned[:277]}..."
        trimmed.append(cleaned)
        if len(trimmed) >= limit:
            break
    return trimmed


def _manual_slack_target(inp: Input) -> tuple[str, str | None]:
    channel = inp.slack_channel.strip()
    if not channel:
        return "", None

    thread_ts = inp.slack_thread_ts.strip() or None
    return channel, thread_ts


def _iteration_prefix(iteration: int) -> str:
    return f"iteration_{iteration}"


async def _call_tool_step(
    ctx: WorkflowContext,
    step_name: str,
    tool: str,
    method: str,
    **kwargs: Any,
) -> Any:
    from api.app import get_tool_manager

    async def _call() -> Any:
        tm = get_tool_manager()
        raw = await tm.call_tool(tool, method, kwargs or {})
        try:
            return json.loads(raw) if isinstance(raw, str) else raw
        except (json.JSONDecodeError, TypeError):
            return {"raw": raw}

    return await ctx.step(step_name, _call, step_kind="tool_call")


async def _post_to_slack_step(
    ctx: WorkflowContext,
    step_name: str,
    channel: str,
    text: str,
    *,
    thread_ts: str | None = None,
) -> dict[str, Any]:
    from api.app import get_tool_manager

    async def _post() -> dict[str, Any]:
        tm = get_tool_manager()
        args: dict[str, Any] = {
            "channel": channel,
            "text": text,
            "no_attribution": True,
        }
        if thread_ts:
            args["thread_ts"] = thread_ts
        raw = await tm.call_tool("slack", "send_message", args)
        try:
            return json.loads(raw) if isinstance(raw, str) else raw
        except (json.JSONDecodeError, TypeError):
            return {"raw": raw}

    return await ctx.step(step_name, _post, step_kind="slack_post")


async def _collect_previous_day_section(
    ctx: WorkflowContext,
    inp: Input,
    *,
    step_prefix: str,
    today_local: dt.date,
) -> dict[str, Any]:
    document = await _call_tool_step(
        ctx,
        f"{step_prefix}.gsuite_docs_get",
        "gsuite",
        "docs_get",
        document_id=_resolve_document_id(inp),
        include_tabs=True,
    )
    tab_text = _extract_tab_text(
        document,
        tab_id=_resolve_tab_id(inp),
        tab_title=inp.doc_tab_title.strip(),
    )
    section_date, section_text = _select_previous_section(tab_text, today=today_local)
    return {
        "date": section_date.isoformat() if section_date else None,
        "text": section_text,
    }


async def _collect_granola_items(
    ctx: WorkflowContext,
    inp: Input,
    *,
    step_prefix: str,
    updated_after: dt.datetime,
) -> list[dict[str, Any]]:
    owner_email = inp.granola_owner_email.strip().lower()
    if not owner_email:
        return []

    notes = await _call_tool_step(
        ctx,
        f"{step_prefix}.granola_list_all_notes",
        "granola",
        "list_all_notes",
        limit=100,
        updated_after=updated_after.isoformat(),
    )
    if not isinstance(notes, list):
        return []

    matching_notes = [
        note for note in notes
        if isinstance(note, dict)
        and ((note.get("owner") or {}).get("email") or "").strip().lower() == owner_email
    ]

    collected: list[dict[str, Any]] = []
    for note_index, note in enumerate(matching_notes[: inp.max_granola_notes], start=1):
        note_id = str(note.get("id") or "").strip()
        if not note_id:
            continue
        transcript = await _call_tool_step(
            ctx,
            f"{step_prefix}.granola_get_transcript_{note_index}",
            "granola",
            "get_transcript",
            note_id=note_id,
        )
        if not isinstance(transcript, list):
            continue

        user_utterances = [
            str(entry.get("text") or "")
            for entry in transcript
            if isinstance(entry, dict)
            and ((entry.get("speaker") or {}).get("source") == "microphone")
            and str(entry.get("text") or "").strip()
        ]
        trimmed = _truncate_utterances(user_utterances)
        if not trimmed:
            continue

        collected.append(
            {
                "title": note.get("title") or "Untitled note",
                "updated_at": note.get("updated_at"),
                "utterances": trimmed,
            }
        )

    return collected


async def _collect_slack_threads(
    ctx: WorkflowContext,
    inp: Input,
    *,
    step_prefix: str,
    previous_day: dt.date,
) -> list[dict[str, Any]]:
    aggregated: dict[str, dict[str, Any]] = {}

    for term_index, term in enumerate(_unique_search_terms(inp), start=1):
        results = await _call_tool_step(
            ctx,
            f"{step_prefix}.slack_search_messages_{term_index}",
            "slack",
            "search_messages",
            query=_slack_query_for_term(term, previous_day),
            max_results=max(inp.max_slack_threads, 1),
            messages_per_channel=100,
        )
        if not isinstance(results, list):
            continue

        for item in results:
            if not isinstance(item, dict):
                continue
            if inp.slack_user_id and item.get("user_id") == inp.slack_user_id:
                continue

            permalink = str(item.get("permalink") or "").strip()
            if not permalink:
                permalink = ":".join(
                    part for part in [
                        str(item.get("channel_id") or "").strip(),
                        str(item.get("thread_ts") or item.get("timestamp") or "").strip(),
                    ]
                    if part
                )
            if not permalink or permalink in aggregated:
                continue

            thread_ts = str(item.get("thread_ts") or item.get("timestamp") or "").strip()
            channel_id = str(item.get("channel_id") or "").strip()
            entry = {
                "channel": item.get("channel"),
                "channel_id": channel_id,
                "message_user": item.get("user"),
                "message_text": _normalize_text(str(item.get("text") or "")),
                "timestamp": item.get("timestamp"),
                "permalink": item.get("permalink"),
                "thread_ts": thread_ts,
                "reply_count": item.get("reply_count") or 0,
            }

            if channel_id and thread_ts and int(entry["reply_count"] or 0) > 0:
                replies = await _call_tool_step(
                    ctx,
                    f"{step_prefix}.slack_get_thread_replies_{len(aggregated) + 1}",
                    "slack",
                    "get_thread_replies",
                    channel_id=channel_id,
                    thread_ts=thread_ts,
                    limit=max(inp.max_thread_replies, 1),
                )
                if isinstance(replies, list):
                    entry["replies"] = [
                        {
                            "user": reply.get("user"),
                            "text": _normalize_text(str(reply.get("text") or "")),
                            "timestamp": reply.get("timestamp"),
                        }
                        for reply in replies[-inp.max_thread_replies :]
                        if isinstance(reply, dict) and str(reply.get("text") or "").strip()
                    ]

            aggregated[permalink] = entry
            if len(aggregated) >= inp.max_slack_threads:
                break
        if len(aggregated) >= inp.max_slack_threads:
            break

    return list(aggregated.values())


def _build_prompt(
    inp: Input,
    *,
    now_local: dt.datetime,
    granola_week_start: dt.date,
    previous_day_section: dict[str, Any],
    granola_items: list[dict[str, Any]],
    slack_threads: list[dict[str, Any]],
) -> str:
    previous_day_date = previous_day_section.get("date") or "unknown"
    previous_day_text = previous_day_section.get("text") or ""
    serialized_granola = json.dumps(granola_items, indent=2)
    serialized_slack = json.dumps(slack_threads, indent=2)
    user_name = inp.slack_user_name.strip() or "the user"

    return (
        f"Prepare {user_name}'s daily checklist for {now_local.date().isoformat()}.\n\n"
        "The final answer will be posted to Slack and copied into a Google Doc, so it must be short,"
        " clear, and immediately actionable.\n\n"
        "Output rules:\n"
        "- Output only Slack-ready markdown. No intro or explanation.\n"
        "- Use `##` section headings and `- [ ]` checklist items.\n"
        "- Deduplicate overlapping tasks across sources.\n"
        "- Prefer specific actions, counterparties, blockers, and deadlines when they exist.\n"
        "- Omit clearly completed items.\n"
        "- Include inline Slack links for Slack-derived items when provided.\n"
        "- Omit empty sections instead of writing filler.\n"
        "- Keep the overall message concise enough for one Slack post.\n\n"
        "Section order:\n"
        f"1. Carryover From {previous_day_date}\n"
        "2. Granola Follow-Ups\n"
        "3. Slack Follow-Ups\n\n"
        f"Current local time: {now_local.isoformat()}\n"
        f"Granola note window: notes updated since the local week of {granola_week_start.isoformat()}.\n"
        "Granola note assumption: only notes owned by the user are included, and the user's own speech"
        " is represented by `speaker.source = \"microphone\"`.\n\n"
        f"Previous day Daily Standup section ({previous_day_date}):\n"
        f"```text\n{previous_day_text}\n```\n\n"
        f"Granola notes:\n```json\n{serialized_granola}\n```\n\n"
        f"Slack mention threads:\n```json\n{serialized_slack}\n```"
    )


async def _run_iteration(inp: Input, ctx: WorkflowContext, *, iteration: int) -> dict[str, Any]:
    timezone = ZoneInfo(inp.timezone)
    now_local = dt.datetime.now(dt.timezone.utc).astimezone(timezone)
    previous_day, previous_day_start_utc = _start_of_previous_day_utc(now_local)
    granola_week_start, granola_week_start_utc = _start_of_week_utc(now_local)
    step_prefix = _iteration_prefix(iteration)

    previous_day_section = await _collect_previous_day_section(
        ctx,
        inp,
        step_prefix=step_prefix,
        today_local=now_local.date(),
    )
    granola_items = await _collect_granola_items(
        ctx,
        inp,
        step_prefix=step_prefix,
        updated_after=granola_week_start_utc,
    )
    slack_threads = await _collect_slack_threads(
        ctx,
        inp,
        step_prefix=step_prefix,
        previous_day=previous_day,
    )
    prompt = _build_prompt(
        inp,
        now_local=now_local,
        granola_week_start=granola_week_start,
        previous_day_section=previous_day_section,
        granola_items=granola_items,
        slack_threads=slack_threads,
    )
    result = await ctx.run_agent(f"{step_prefix}.agent_turn", text=prompt)
    result_text = ""
    if isinstance(result, dict):
        result_text = str(result.get("result_text") or "").strip()

    slack_channel, slack_thread_ts = _manual_slack_target(inp)
    if result_text and slack_channel:
        await _post_to_slack_step(
            ctx,
            f"{step_prefix}.post_slack",
            slack_channel,
            result_text,
            thread_ts=slack_thread_ts,
        )

    return {
        "ran_at": now_local.isoformat(),
        "granola_week_start": granola_week_start.isoformat(),
        "previous_day_section": previous_day_section,
        "granola_items": granola_items,
        "slack_threads": slack_threads,
        "slack_posted_to": slack_channel or None,
        "slack_thread_ts": slack_thread_ts,
        "result": result,
    }


async def handler(inp: Input, ctx: WorkflowContext) -> dict[str, Any]:
    document_id = _resolve_document_id(inp)
    if not document_id:
        raise ControlPlaneError(
            "INVALID_WORKFLOW_INPUT",
            "daily_checklist_digest requires a valid Google Doc identifier",
            422,
        )
    if not inp.doc_tab_title.strip() and not _resolve_tab_id(inp):
        raise ControlPlaneError(
            "INVALID_WORKFLOW_INPUT",
            "daily_checklist_digest requires doc_tab_title or doc_tab_id",
            422,
        )

    iteration = 0
    last_result: dict[str, Any] = {}

    if inp.send_immediately:
        iteration += 1
        last_result = await _run_iteration(inp, ctx, iteration=iteration)
        if inp.max_iterations > 0 and iteration >= inp.max_iterations:
            return {"status": "done", "iterations": iteration, "last_result": last_result}

    while True:
        now_local = dt.datetime.now(dt.timezone.utc).astimezone(ZoneInfo(inp.timezone))
        next_iteration = iteration + 1
        await ctx.sleep(
            f"wait_until_next_run_{next_iteration}",
            _next_run_delta(
                now_local,
                run_hour=max(0, min(inp.run_hour, 23)),
                run_minute=max(0, min(inp.run_minute, 59)),
            ),
        )
        iteration = next_iteration
        last_result = await _run_iteration(inp, ctx, iteration=iteration)
        if inp.max_iterations > 0 and iteration >= inp.max_iterations:
            return {"status": "done", "iterations": iteration, "last_result": last_result}
