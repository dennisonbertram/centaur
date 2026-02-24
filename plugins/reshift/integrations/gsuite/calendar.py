"""Google Calendar API client."""

from datetime import datetime, timedelta

from googleapiclient.discovery import build

from .auth import get_credentials


def get_calendar_service():
    """Get authenticated Calendar service."""
    creds = get_credentials()
    if not creds:
        raise RuntimeError("Not authenticated. Run `reshift auth` first.")
    return build("calendar", "v3", credentials=creds)


def get_upcoming_events(
    days: int = 7, max_results: int = 20, calendar_id: str = "primary"
) -> list[dict]:
    """Get upcoming calendar events."""
    service = get_calendar_service()

    now = datetime.utcnow()
    time_min = now.isoformat() + "Z"
    time_max = (now + timedelta(days=days)).isoformat() + "Z"

    events_result = (
        service.events()
        .list(
            calendarId=calendar_id,
            timeMin=time_min,
            timeMax=time_max,
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )

    events = events_result.get("items", [])
    return [
        {
            "id": e["id"],
            "summary": e.get("summary", "No title"),
            "start": e["start"].get("dateTime", e["start"].get("date")),
            "end": e["end"].get("dateTime", e["end"].get("date")),
            "attendees": [a.get("email") for a in e.get("attendees", [])],
            "description": e.get("description", ""),
            "location": e.get("location", ""),
            "meeting_link": e.get("hangoutLink", ""),
        }
        for e in events
    ]


def create_event(
    summary: str,
    start_time: datetime,
    end_time: datetime,
    attendees: list[str],
    description: str = "",
    location: str = "",
    calendar_id: str = "primary",
    send_notifications: bool = True,
) -> dict:
    """Create a calendar event with attendees."""
    service = get_calendar_service()

    event = {
        "summary": summary,
        "location": location,
        "description": description,
        "start": {
            "dateTime": start_time.isoformat(),
            "timeZone": "America/Los_Angeles",
        },
        "end": {
            "dateTime": end_time.isoformat(),
            "timeZone": "America/Los_Angeles",
        },
        "attendees": [{"email": email} for email in attendees],
    }

    created_event = (
        service.events()
        .insert(
            calendarId=calendar_id,
            body=event,
            sendNotifications=send_notifications,
        )
        .execute()
    )

    return {
        "id": created_event["id"],
        "summary": created_event.get("summary"),
        "html_link": created_event.get("htmlLink"),
        "meeting_link": created_event.get("hangoutLink"),
        "start": created_event["start"].get("dateTime"),
        "attendees": [a.get("email") for a in created_event.get("attendees", [])],
    }


def get_past_events(
    days: int = 7, max_results: int = 20, calendar_id: str = "primary"
) -> list[dict]:
    """Get past calendar events (for meeting context)."""
    service = get_calendar_service()

    now = datetime.utcnow()
    time_max = now.isoformat() + "Z"
    time_min = (now - timedelta(days=days)).isoformat() + "Z"

    events_result = (
        service.events()
        .list(
            calendarId=calendar_id,
            timeMin=time_min,
            timeMax=time_max,
            maxResults=max_results,
            singleEvents=True,
            orderBy="startTime",
        )
        .execute()
    )

    events = events_result.get("items", [])
    return [
        {
            "id": e["id"],
            "summary": e.get("summary", "No title"),
            "start": e["start"].get("dateTime", e["start"].get("date")),
            "attendees": [a.get("email") for a in e.get("attendees", [])],
            "description": e.get("description", ""),
        }
        for e in events
    ]
