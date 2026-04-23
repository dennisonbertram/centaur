"""Workflow: monitors SF conference rooms and alerts #sf-ops-team on double-bookings."""

from __future__ import annotations

import datetime as dt
from dataclasses import dataclass
from typing import Any

from api.workflow_engine import WorkflowContext

WORKFLOW_NAME = "room_conflict_monitor"

ROOM_EMAILS = [
    "paradigm.xyz_188fm3e1sqa38h6alb7s452fnlu6q6gb74oj0c9o6co3ad9p6k@resource.calendar.google.com",
    "paradigm.xyz_188boiki4jtm2js3n7uq5mfr58k6q6gb74o34cpl70s32chi70@resource.calendar.google.com",
    "paradigm.xyz_188f57ur7em5cimjkten5t7idbboi6ga64sjgd9k6cq36c9p@resource.calendar.google.com",
    "paradigm.xyz_188234cm1s0e2iovm8o8dorookjbi6ga70s32dhn6cpjad1m@resource.calendar.google.com",
    "c_1885pkq3qntfegbci3c612ki3eh6e@resource.calendar.google.com",
    "c_1880lsqsr6ks8irlkssgnfar0if02@resource.calendar.google.com",
]


@dataclass
class Input:
    slack_channel: str = "sf-ops-team"
    check_interval_seconds: int = 60
    lookahead_days: int = 7
    max_iterations: int = 0  # 0 = run forever


async def handler(inp: Input, ctx: WorkflowContext) -> dict[str, Any]:
    """Poll all accessible user calendars for room bookings and alert on double-bookings."""

    seen_conflict_keys: list[str] = []
    iteration = 0

    while True:
        iteration += 1

        result = await ctx.run_agent(
            f"check_{iteration}",
            text=f"""You are monitoring SF conference rooms for double-bookings. Follow these steps exactly.

ROOM RESOURCE EMAILS TO WATCH:
{chr(10).join(f"- {r}" for r in ROOM_EMAILS)}

ALREADY-REPORTED CONFLICTS (skip these):
{seen_conflict_keys}

STEPS:

1. Call gsuite `calendar_list` to get all accessible calendars.

2. For each calendar returned, call gsuite `calendar_events` with that calendar's ID
   to fetch all events from now through {inp.lookahead_days} days from now.
   Use max_results=100.

3. From all fetched events, keep only events where at least one attendee email
   matches one of the ROOM RESOURCE EMAILS above. These are room bookings.

4. Group the room bookings by the matched room email.

5. Within each room group, check every pair of events for a time overlap:
     event_a.start < event_b.end  AND  event_a.end > event_b.start

6. For each overlapping pair compute a conflict key:
     "<room_email>::<alphabetically_first_event_id>|<alphabetically_second_event_id>"

7. Skip any key already in ALREADY-REPORTED CONFLICTS.

8. For each NEW conflict:
   a. The newer event (higher `created` timestamp) is the booking causing the conflict.
   b. Send a Slack message to channel #{inp.slack_channel}:

      🚨 *Room Conflict Detected*
      *Room:* <room name from the attendee displayName field>
      *New booking by:* <organizer.displayName of the newer event>
      *Event:* "<newer event summary>"
      *Time:* <day of week, date, start time – end time in PT>
      *Conflicts with:* "<older event summary>" (organized by <older event organizer.displayName>)

9. Return JSON: {{"new_conflict_keys": ["key1", ...]}}
   Return {{"new_conflict_keys": []}} if no new conflicts.
""",
        )

        # Accumulate seen conflicts so we never double-alert
        if isinstance(result, dict):
            new_keys = result.get("new_conflict_keys", [])
            if isinstance(new_keys, list):
                for k in new_keys:
                    if k not in seen_conflict_keys:
                        seen_conflict_keys.append(k)

        if inp.max_iterations > 0 and iteration >= inp.max_iterations:
            return {"status": "done", "iterations": iteration}

        await ctx.sleep(
            f"wait_{iteration}",
            dt.timedelta(seconds=inp.check_interval_seconds),
        )
