"""Reshift plugin — Paradigm I&R Knowledge Platform."""

from __future__ import annotations

try:
    from ai_v2.plugin_sdk import plugin_tool
except ImportError:

    def plugin_tool(*, name=None):
        def decorator(fn):
            fn.__plugin_tool__ = name or fn.__name__
            return fn
        return decorator


@plugin_tool()
def db_query(query: str, limit: int = 20) -> list[dict]:
    """Execute a read-only SQL query against Paradigm's internal PostgreSQL database.

    Args:
        query: SQL query to execute
        limit: Max rows to return
    """
    from .integrations.database import get_db
    from .integrations.database.client import is_tunnel_running, start_persistent_tunnel

    if not is_tunnel_running():
        start_persistent_tunnel()

    db = get_db()
    results = db.query(query)
    return results[:limit] if results else []


@plugin_tool()
def db_tables() -> list[str]:
    """List all tables in the internal database."""
    from .integrations.database import get_db
    from .integrations.database.client import is_tunnel_running, start_persistent_tunnel

    if not is_tunnel_running():
        start_persistent_tunnel()

    db = get_db()
    return db.list_tables()


@plugin_tool()
def db_describe(table_name: str) -> list[dict]:
    """Describe columns of a database table.

    Args:
        table_name: Name of the table to describe
    """
    from .integrations.database import get_db
    from .integrations.database.client import is_tunnel_running, start_persistent_tunnel

    if not is_tunnel_running():
        start_persistent_tunnel()

    db = get_db()
    return db.describe_table(table_name)


@plugin_tool()
def notes_search(query: str, note_type: str = "", limit: int = 20) -> list[dict]:
    """Search Shift notes from the investment process.

    Args:
        query: Search text
        note_type: Filter by type (OPPORTUNITY, PORTCO_UPDATE, PORTCO_REVIEW, TALENT, GTM, etc.)
        limit: Max results
    """
    from .integrations.database.client import is_tunnel_running, start_persistent_tunnel
    from .integrations.notes import get_notes_client

    if not is_tunnel_running():
        start_persistent_tunnel()

    client = get_notes_client()
    notes = client.search_notes(query, note_type=note_type or None, limit=limit)
    return [
        {
            "id": n.id,
            "title": n.title,
            "type": n.note_type,
            "created_at": n.created_at.isoformat(),
            "created_by": n.created_by_name,
            "notes": n.notes[:500],
        }
        for n in notes
    ]


@plugin_tool()
def notes_read(note_id: str) -> dict:
    """Read a full Shift note by ID.

    Args:
        note_id: The note ID
    """
    from .integrations.database.client import is_tunnel_running, start_persistent_tunnel
    from .integrations.notes import get_notes_client

    if not is_tunnel_running():
        start_persistent_tunnel()

    client = get_notes_client()
    data = client.get_note_with_relations(note_id)
    if not data:
        return {"error": f"Note '{note_id}' not found"}

    note = data["note"]
    return {
        "id": note.id,
        "title": note.title,
        "type": note.note_type,
        "source": note.source,
        "created_at": note.created_at.isoformat(),
        "created_by": note.created_by_name,
        "organizations": data["organizations"],
        "people": data["people"],
        "notes": note.notes,
    }


@plugin_tool()
def notes_stats() -> dict:
    """Get statistics about Shift notes."""
    from .integrations.database.client import is_tunnel_running, start_persistent_tunnel
    from .integrations.notes import get_notes_client

    if not is_tunnel_running():
        start_persistent_tunnel()

    client = get_notes_client()
    return client.get_stats()


@plugin_tool()
def email_search(query: str, limit: int = 10) -> list[dict]:
    """Search Gmail emails.

    Args:
        query: Gmail search query
        limit: Max results
    """
    from .integrations.gsuite.gmail import search_emails

    return search_emails(query, max_results=limit)


@plugin_tool()
def calendar_events(days: int = 7, past: bool = False, limit: int = 10) -> list[dict]:
    """Get calendar events.

    Args:
        days: Number of days to look ahead (or back if past=True)
        past: Show past events instead of upcoming
        limit: Max results
    """
    from .integrations.gsuite.calendar import get_past_events, get_upcoming_events

    if past:
        return get_past_events(days=days, max_results=limit)
    return get_upcoming_events(days=days, max_results=limit)


@plugin_tool()
def drive_search(query: str, limit: int = 10) -> list[dict]:
    """Search Google Drive files.

    Args:
        query: Search query
        limit: Max results
    """
    from .integrations.gsuite.drive import search_files

    return search_files(query, max_results=limit)
