"""CLI entrypoint for Reshift."""

from dotenv import load_dotenv

load_dotenv()

import typer
from rich.console import Console
from ai_v2.cli_tables import Table

app = typer.Typer(name="reshift", help="Paradigm I&R Knowledge Platform")
console = Console()


@app.command()
def bot():
    """Start the Slack bot (Socket Mode)."""
    from .bot import run_bot

    run_bot()


@app.command()
def auth():
    """Authenticate with Google APIs."""
    from .integrations.gsuite.auth import authenticate

    authenticate()


@app.command()
def skills(query: str = typer.Argument(..., help="Query to search skills")):
    """Query the skills knowledge base."""
    from .skills.search import search_skills

    search_skills(query)


@app.command()
def emails(
    query: str = typer.Argument("", help="Gmail search query"),
    limit: int = typer.Option(10, "--limit", "-n", help="Max results"),
    body: bool = typer.Option(False, "--body", "-b", help="Show full body of first result"),
):
    """Search your emails."""
    from .integrations.gsuite.gmail import get_email_body, search_emails

    results = search_emails(query, max_results=limit)

    if not results:
        console.print("[yellow]No emails found.[/]")
        return

    table = Table(title=f"Emails matching '{query}'" if query else "Recent Emails")
    table.add_column("From", style="cyan", max_width=30)
    table.add_column("Subject", style="white", max_width=50)
    table.add_column("Date", style="dim", max_width=20)

    for e in results:
        table.add_row(e["from"][:30], e["subject"][:50], e["date"][:20])

    console.print(table)

    if body and results:
        console.print("\n[bold]Body of first email:[/]\n")
        console.print(get_email_body(results[0]["id"]))


@app.command()
def calendar(
    days: int = typer.Option(7, "--days", "-d", help="Days to look ahead"),
    past: bool = typer.Option(False, "--past", "-p", help="Show past events instead"),
    limit: int = typer.Option(10, "--limit", "-n", help="Max results"),
    user: str = typer.Option("primary", "--user", "-u", help="Calendar ID or email"),
):
    """Show calendar events."""
    from .integrations.gsuite.calendar import get_past_events, get_upcoming_events

    calendar_id = user

    if past:
        events = get_past_events(days=days, max_results=limit, calendar_id=calendar_id)
        title = f"Past {days} days" + (f" ({user})" if user != "primary" else "")
    else:
        events = get_upcoming_events(days=days, max_results=limit, calendar_id=calendar_id)
        title = f"Next {days} days" + (f" ({user})" if user != "primary" else "")

    if not events:
        console.print("[yellow]No events found.[/]")
        return

    table = Table(title=title)
    table.add_column("When", style="cyan", max_width=20)
    table.add_column("Event", style="white", max_width=40)
    table.add_column("Attendees", style="dim", max_width=30)

    for e in events:
        start = e["start"][:16] if "T" in e["start"] else e["start"]
        attendees = ", ".join(a.split("@")[0] for a in e["attendees"][:3])
        if len(e["attendees"]) > 3:
            attendees += f" +{len(e['attendees']) - 3}"
        table.add_row(start, e["summary"][:40], attendees)

    console.print(table)


@app.command()
def drive(
    query: str = typer.Argument(..., help="Search query"),
    limit: int = typer.Option(10, "--limit", "-n", help="Max results"),
    read: bool = typer.Option(False, "--read", "-r", help="Read content of first result"),
):
    """Search Google Drive."""
    from .integrations.gsuite.drive import get_file_content, search_files

    results = search_files(query, max_results=limit)

    if not results:
        console.print("[yellow]No files found.[/]")
        return

    table = Table(title=f"Drive files matching '{query}'")
    table.add_column("Name", style="cyan", max_width=50)
    table.add_column("Type", style="dim", max_width=20)
    table.add_column("Modified", style="dim", max_width=12)

    type_map = {
        "application/vnd.google-apps.document": "Doc",
        "application/vnd.google-apps.spreadsheet": "Sheet",
        "application/vnd.google-apps.presentation": "Slides",
        "application/pdf": "PDF",
    }

    for f in results:
        ftype = type_map.get(f["mimeType"], f["mimeType"].split("/")[-1][:15])
        modified = f["modifiedTime"][:10]
        table.add_row(f["name"][:50], ftype, modified)

    console.print(table)

    if read and results:
        console.print(f"\n[bold]Content of '{results[0]['name']}':[/]\n")
        try:
            content = get_file_content(results[0]["id"])
            console.print(content[:3000])
            if len(content) > 3000:
                console.print(f"\n[dim]... truncated ({len(content)} chars total)[/]")
        except Exception as e:
            console.print(f"[red]Could not read file: {e}[/]")


@app.command()
def ask(
    question: str = typer.Argument(..., help="Question to ask"),
):
    """Ask a question using all available context."""
    from .slack.handlers import handle_query

    response = handle_query(question)
    console.print(response)


@app.command()
def db(
    query: str = typer.Argument(None, help="SQL query to execute"),
    tables: bool = typer.Option(False, "--tables", "-t", help="List all tables"),
    describe: str = typer.Option(None, "--describe", "-d", help="Describe a table"),
    funds: bool = typer.Option(False, "--funds", "-f", help="List funds"),
    assets: bool = typer.Option(False, "--assets", "-a", help="List assets"),
    limit: int = typer.Option(20, "--limit", "-n", help="Max results"),
    tunnel: bool = typer.Option(False, "--tunnel", help="Start persistent SSH tunnel"),
    close: bool = typer.Option(False, "--close", help="Close persistent SSH tunnel"),
):
    """Query Paradigm's internal PostgreSQL database.

    The tunnel is started automatically on first query and persists across commands.
    Use --close to stop the tunnel when done.
    """
    from .integrations.database import get_db
    from .integrations.database.client import (
        is_tunnel_running,
        start_persistent_tunnel,
        stop_persistent_tunnel,
    )

    if close:
        if stop_persistent_tunnel():
            console.print("[green]SSH tunnel closed.[/]")
        else:
            console.print("[yellow]No tunnel running.[/]")
        return

    if tunnel:
        if is_tunnel_running():
            console.print("[green]SSH tunnel already running.[/]")
        else:
            start_persistent_tunnel()
            console.print("[green]SSH tunnel started.[/]")
        return

    # Auto-start tunnel if not running
    if not is_tunnel_running():
        console.print("[dim]Starting SSH tunnel...[/]")
        start_persistent_tunnel()

    db = get_db()

    try:
        if tables:
            table_list = db.list_tables()
            table = Table(title="Database Tables")
            table.add_column("Table Name", style="cyan")
            for t in table_list:
                table.add_row(t)
            console.print(table)

        elif describe:
            cols = db.describe_table(describe)
            if not cols:
                console.print(f"[yellow]Table '{describe}' not found.[/]")
                return
            table = Table(title=f"Table: {describe}")
            table.add_column("Column", style="cyan")
            table.add_column("Type", style="green")
            table.add_column("Nullable", style="dim")
            for c in cols:
                table.add_row(c["column_name"], c["data_type"], c["is_nullable"])
            console.print(table)

        elif funds:
            results = db.get_funds(limit=limit)
            table = Table(title="Funds")
            if results:
                for key in results[0].keys():
                    table.add_column(str(key), max_width=30)
                for r in results:
                    table.add_row(*[str(v)[:30] for v in r.values()])
            console.print(table)

        elif assets:
            results = db.get_assets(limit=limit)
            table = Table(title="Assets")
            if results:
                for key in list(results[0].keys())[:6]:
                    table.add_column(str(key), max_width=25)
                for r in results:
                    table.add_row(*[str(v)[:25] for v in list(r.values())[:6]])
            console.print(table)

        elif query:
            results = db.query(query)
            if not results:
                console.print("[yellow]No results.[/]")
                return
            table = Table(title="Query Results")
            for key in list(results[0].keys())[:8]:
                table.add_column(str(key), max_width=30)
            for r in results[:limit]:
                table.add_row(*[str(v)[:30] for v in list(r.values())[:8]])
            console.print(table)
            if len(results) > limit:
                console.print(f"[dim]... showing {limit} of {len(results)} results[/]")

        else:
            console.print(
                "[yellow]Provide a query or use --tables, --describe, --funds, --assets[/]"
            )

    except Exception as e:
        error_str = str(e).lower()
        console.print(f"[red]Database error: {e}[/]")
        # Only suggest tunnel check for connection errors, not schema/SQL errors
        if any(
            hint in error_str
            for hint in ["connection refused", "could not connect", "timeout", "no route"]
        ):
            console.print("[dim]Make sure the bastion SSH tunnel is running.[/]")


@app.command()
def bq(
    query: str = typer.Argument(None, help="BigQuery SQL query to execute"),
    tables: bool = typer.Option(False, "--tables", "-t", help="List all tables/views"),
    describe: str = typer.Option(None, "--describe", "-d", help="Describe a table/view"),
    ticker: str = typer.Option(None, "--ticker", help="Filter transactions by ticker symbol"),
    fund: str = typer.Option(None, "--fund", "-f", help="Filter by fund (PF, P1, P2)"),
    txn_type: str = typer.Option(None, "--type", help="Filter by transaction type"),
    start_date: str = typer.Option(None, "--start", help="Start date (YYYY-MM-DD)"),
    end_date: str = typer.Option(None, "--end", help="End date (YYYY-MM-DD)"),
    limit: int = typer.Option(20, "--limit", "-n", help="Max results"),
):
    """Query BigQuery views in custody-dashboard.shift_prod_public_views.

    Examples:
        reshift bq --tables                                  # List available views
        reshift bq -d transactions_csv                       # Describe transactions table
        reshift bq --ticker HYPE --start 2026-01-01          # HYPE transactions in 2026
        reshift bq --ticker HYPE --type staking              # HYPE staking rewards
        reshift bq "SELECT * FROM transactions_csv LIMIT 5"  # Raw SQL query
    """
    from .integrations.database.bigquery import (
        describe_table,
        get_transactions,
        list_tables,
        query_bigquery,
    )

    try:
        if tables:
            table_list = list_tables()
            table = Table(title="BigQuery Views (custody-dashboard.shift_prod_public_views)")
            table.add_column("Table/View Name", style="cyan")
            for t in table_list:
                table.add_row(t)
            console.print(table)

        elif describe:
            cols = describe_table(describe)
            if not cols:
                console.print(f"[yellow]Table '{describe}' not found.[/]")
                return
            table = Table(title=f"Table: {describe}")
            table.add_column("Column", style="cyan")
            table.add_column("Type", style="green")
            table.add_column("Mode", style="dim")
            for c in cols:
                table.add_row(c["column_name"], c["data_type"], c["mode"])
            console.print(table)

        elif ticker or fund or txn_type or start_date or end_date:
            results = get_transactions(
                ticker=ticker,
                fund=fund,
                transaction_type=txn_type,
                start_date=start_date,
                end_date=end_date,
                limit=limit,
            )
            if not results:
                console.print("[yellow]No transactions found.[/]")
                return
            table = Table(title="Transactions")
            for key in list(results[0].keys())[:8]:
                table.add_column(str(key), max_width=25)
            for r in results[:limit]:
                table.add_row(*[str(v)[:25] for v in list(r.values())[:8]])
            console.print(table)

        elif query:
            full_query = query
            if "FROM " in query.upper() and "`" not in query:
                import re

                full_query = re.sub(
                    r"\bFROM\s+(\w+)",
                    r"FROM `custody-dashboard.shift_prod_public_views.\1`",
                    query,
                    flags=re.IGNORECASE,
                )
            results = query_bigquery(full_query, limit)
            if not results:
                console.print("[yellow]No results.[/]")
                return
            table = Table(title="Query Results")
            for key in list(results[0].keys())[:8]:
                table.add_column(str(key), max_width=30)
            for r in results[:limit]:
                table.add_row(*[str(v)[:30] for v in list(r.values())[:8]])
            console.print(table)

        else:
            console.print(
                "[yellow]Provide a query, --tables, --describe, or transaction filters[/]"
            )

    except Exception as e:
        console.print(f"[red]BigQuery error: {e}[/]")
        console.print("[dim]Ensure svc_ai@paradigm.xyz has BigQuery access to custody-dashboard[/]")


@app.command()
def figma(
    url: str = typer.Argument(..., help="Figma file or frame URL"),
    json_output: bool = typer.Option(False, "--json", "-j", help="Output as JSON"),
):
    """Crawl a Figma file and extract design system info.

    Extracts colors, typography, components, variables, and frames from any Figma URL.
    Uses FIGMA env var for authentication (personal access token).
    """
    from .integrations.figma import FigmaClient

    try:
        client = FigmaClient()
        ds = client.crawl(url)
    except ValueError as e:
        console.print(f"[red]{e}[/]")
        return
    except Exception as e:
        console.print(f"[red]Figma API error: {e}[/]")
        return

    if json_output:
        import json
        import sys

        output = {
            "file_name": ds.file_name,
            "colors": ds.colors,
            "text_styles": ds.text_styles,
            "components": ds.components,
            "variables": ds.variables,
            "frames": ds.frames,
            "effects": ds.effects,
            "grids": ds.grids,
        }
        print(json.dumps(output, indent=2, ensure_ascii=True), file=sys.stdout)
        return

    console.print(f"\n[bold]{ds.file_name}[/]\n")

    # Colors
    if ds.colors:
        table = Table(title="Colors")
        table.add_column("Color", style="cyan", max_width=20)
        table.add_column("Name/Source", style="white", max_width=40)
        seen = set()
        for c in ds.colors:
            val = c.get("value") or c.get("name", "")
            if val in seen:
                continue
            seen.add(val)
            source = c.get("source") or c.get("description", "")
            table.add_row(val, source[:40])
        console.print(table)

    # Typography
    if ds.text_styles:
        table = Table(title="Typography")
        table.add_column("Font", style="cyan", max_width=25)
        table.add_column("Size", style="green", max_width=8)
        table.add_column("Weight", style="dim", max_width=8)
        table.add_column("Line Height", style="dim", max_width=12)
        for t in ds.text_styles:
            font = t.get("fontFamily") or t.get("name", "")
            size = str(t.get("fontSize", "")) if t.get("fontSize") else ""
            weight = str(t.get("fontWeight", "")) if t.get("fontWeight") else ""
            lh = f"{t['lineHeight']:.1f}px" if t.get("lineHeight") else ""
            table.add_row(font, size, weight, lh)
        console.print(table)

    # Components
    if ds.components:
        table = Table(title="Components")
        table.add_column("Name", style="cyan", max_width=40)
        table.add_column("Description", style="dim", max_width=50)
        for c in ds.components:
            table.add_row(c["name"], c.get("description", "")[:50])
        console.print(table)

    # Variables
    if ds.variables:
        table = Table(title="Variables")
        table.add_column("Name", style="cyan", max_width=30)
        table.add_column("Type", style="green", max_width=15)
        for v in ds.variables:
            table.add_row(v["name"], v.get("type", ""))
        console.print(table)

    # Frames
    if ds.frames:
        table = Table(title="Frames")
        table.add_column("Name", style="cyan", max_width=40)
        table.add_column("Size", style="green", max_width=15)
        table.add_column("Background", style="dim", max_width=20)
        for f in ds.frames:
            w, h = f.get("width"), f.get("height")
            size = f"{int(w)}x{int(h)}" if w and h else ""
            bg = f.get("background") or ""
            table.add_row(f["name"], size, bg)
        console.print(table)

    # Summary
    console.print(
        f"\n[dim]Found: {len(ds.colors)} colors, {len(ds.text_styles)} text styles, "
        f"{len(ds.components)} components, {len(ds.variables)} variables, "
        f"{len(ds.frames)} frames[/]"
    )


@app.command(name="slack-search")
def slack_search(
    query: str = typer.Argument(..., help="Slack search query"),
    limit: int = typer.Option(10, "--limit", "-n", help="Max results"),
    body: bool = typer.Option(False, "--body", "-b", help="Show full text of first result"),
    full: bool = typer.Option(False, "--full", "-f", help="Show full text of all results"),
    links: bool = typer.Option(False, "--links", "-l", help="Show permalinks for each message"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Search Slack messages.

    Supports Slack search operators:
    - from:@username - Messages from a user
    - in:#channel - Messages in a channel
    - has:link / has:emoji / has:reaction - Filter by content type
    - before:2024-01-01 / after:2024-01-01 - Date filters
    - "exact phrase" - Exact match

    Examples:
        reshift slack-search "in:#investing uniswap" -n 20
        reshift slack-search "from:@arjun defi" --body
        reshift slack-search "in:#experiment-twitter-tracking" --full --json
    """
    import json
    import sys

    from .integrations.slack.client import search_messages

    results = search_messages(query, max_results=limit)

    if not results:
        console.print("[yellow]No messages found.[/]")
        return

    if json_output:
        print(json.dumps(results, indent=2, ensure_ascii=False), file=sys.stdout)
        return

    if full:
        # Show full text for all messages
        console.print(f"\n[bold]Slack messages matching '{query}'[/]\n")
        for msg in results:
            console.print(f"[cyan]#{msg['channel']}[/] | [green]@{msg['user']}[/]")
            console.print(msg["text"])
            if links:
                console.print(f"[dim]{msg.get('permalink', '')}[/]")
            console.print()
        return

    table = Table(title=f"Slack messages matching '{query}'")
    table.add_column("Channel", style="cyan", max_width=15)
    table.add_column("User", style="green", max_width=15)
    table.add_column("Message", style="white", max_width=60)
    if links:
        table.add_column("Link", style="blue", max_width=80)

    for msg in results:
        text = msg["text"][:60].replace("\n", " ")
        if len(msg["text"]) > 60:
            text += "..."
        if links:
            table.add_row(f"#{msg['channel']}", msg["user"], text, msg.get("permalink", ""))
        else:
            table.add_row(f"#{msg['channel']}", msg["user"], text)

    console.print(table)

    if body and results:
        console.print("\n[bold]Full text of first result:[/]\n")
        console.print(f"[cyan]#{results[0]['channel']}[/] | [green]@{results[0]['user']}[/]")
        console.print(results[0]["text"])
        console.print(f"\n[dim]Permalink: {results[0].get('permalink', '')}[/]")


@app.command(name="slack-channel")
def slack_channel(
    channel: str = typer.Argument(..., help="Channel name (without #) or channel ID"),
    limit: int = typer.Option(50, "--limit", "-n", help="Max messages to fetch"),
    full: bool = typer.Option(False, "--full", "-f", help="Show full message text"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Get recent messages from a Slack channel.

    Unlike slack-search, this fetches actual channel history (not search results),
    showing messages in chronological order.

    Examples:
        reshift slack-channel investing -n 30
        reshift slack-channel experiment-twitter-tracking --full
        reshift slack-channel C01234567 --json
    """
    import json
    import sys

    from .integrations.slack.client import get_channel_history

    try:
        messages = get_channel_history(channel, limit=limit)
    except RuntimeError as e:
        console.print(f"[red]{e}[/]")
        return

    if not messages:
        console.print("[yellow]No messages found.[/]")
        return

    if json_output:
        print(json.dumps(messages, indent=2, ensure_ascii=False), file=sys.stdout)
        return

    console.print(f"\n[bold]Recent messages from #{channel}[/] ({len(messages)} messages)\n")

    if full:
        for msg in messages:
            reply_count = msg.get("reply_count", 0)
            thread_indicator = f" [dim](+{reply_count} replies)[/]" if reply_count > 0 else ""
            console.print(f"[green]@{msg['user']}[/]{thread_indicator}")
            console.print(msg["text"])
            console.print()
    else:
        table = Table()
        table.add_column("User", style="green", max_width=15)
        table.add_column("Message", style="white", max_width=80)
        table.add_column("Replies", style="dim", max_width=8)

        for msg in messages:
            text = msg["text"][:80].replace("\n", " ")
            if len(msg["text"]) > 80:
                text += "..."
            replies = str(msg.get("reply_count", 0)) if msg.get("reply_count", 0) > 0 else ""
            table.add_row(f"@{msg['user']}", text, replies)

        console.print(table)


@app.command(name="slack-channels")
def slack_channels(
    public_only: bool = typer.Option(False, "--public-only", help="Only show public channels"),
    filter_text: str = typer.Option(None, "--filter", "-f", help="Filter by name/purpose"),
):
    """List Slack channels with metadata (includes private by default)."""
    from .integrations.slack.client import list_channels

    channels = list_channels(include_private=not public_only, limit=10000)

    if filter_text:
        filter_lower = filter_text.lower()
        channels = [
            c
            for c in channels
            if filter_lower in c["name"].lower() or filter_lower in c["purpose"].lower()
        ]

    if not channels:
        console.print("[yellow]No channels found.[/]")
        return

    table = Table(title="Slack Channels")
    table.add_column("Channel", style="cyan", max_width=30)
    table.add_column("Members", style="green", justify="right", max_width=8)
    table.add_column("Purpose", style="white", max_width=50)

    for ch in channels:
        purpose = ch["purpose"][:50] if ch["purpose"] else ""
        if len(ch["purpose"]) > 50:
            purpose += "..."
        name = f"#{ch['name']}"
        if ch["is_private"]:
            name = f"🔒 {name}"
        table.add_row(name, str(ch["member_count"]), purpose)

    console.print(table)
    console.print(f"[dim]Total: {len(channels)} channels[/]")


@app.command(name="slack-users")
def slack_users(
    limit: int = typer.Option(500, "--limit", "-n", help="Max users to list"),
    filter_text: str = typer.Option(None, "--filter", "-f", help="Filter by name/email/title"),
    no_bots: bool = typer.Option(True, "--no-bots", help="Exclude bots"),
):
    """List Slack workspace members with metadata."""
    from .integrations.slack.client import list_users

    users = list_users(limit=limit)

    if no_bots:
        users = [u for u in users if not u["is_bot"]]

    if filter_text:
        filter_lower = filter_text.lower()
        users = [
            u
            for u in users
            if filter_lower in u["name"].lower()
            or filter_lower in u["real_name"].lower()
            or filter_lower in (u["email"] or "").lower()
            or filter_lower in (u["title"] or "").lower()
        ]

    if not users:
        console.print("[yellow]No users found.[/]")
        return

    table = Table(title="Slack Users")
    table.add_column("Handle", style="cyan", max_width=15)
    table.add_column("Name", style="green", max_width=25)
    table.add_column("Email", style="white", max_width=30)
    table.add_column("Title", style="dim", max_width=30)

    for user in users:
        email = user["email"] or ""
        title = user["title"] or ""
        if len(title) > 30:
            title = title[:27] + "..."
        table.add_row(f"@{user['name']}", user["real_name"], email, title)

    console.print(table)
    console.print(f"[dim]Total: {len(users)} users[/]")


@app.command()
def notes(
    query: str = typer.Argument(None, help="Search query (omit to list recent notes)"),
    note_type: str = typer.Option(
        None,
        "--type",
        "-t",
        help="Filter by type: OPPORTUNITY, PORTCO_UPDATE, PORTCO_REVIEW, TALENT, GTM, etc.",
    ),
    org: str = typer.Option(None, "--org", "-o", help="Filter by organization name"),
    limit: int = typer.Option(20, "--limit", "-n", help="Max results"),
    read: str = typer.Option(None, "--read", "-r", help="Read full note by ID"),
    stats: bool = typer.Option(False, "--stats", "-s", help="Show note statistics"),
    authors: bool = typer.Option(False, "--authors", "-a", help="Show top authors"),
    full: bool = typer.Option(False, "--full", "-f", help="Show full note text (not truncated)"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Search and read Shift notes from the investment process.

    Note types:
        OPPORTUNITY     - Investment opportunities
        PORTCO_UPDATE   - Portfolio company updates
        PORTCO_REVIEW   - Portfolio company reviews
        TALENT          - Hiring/recruiting notes
        GTM             - Go-to-market notes
        DESIGN          - Design team notes
        LEGAL_POLICY    - Legal/policy notes
        OTHER           - Miscellaneous

    Examples:
        reshift notes                           # Recent notes
        reshift notes "uniswap"                 # Search for Uniswap
        reshift notes -t OPPORTUNITY            # Investment opportunities
        reshift notes -o "Uniswap" -n 10        # Notes about Uniswap org
        reshift notes --read abc123             # Read full note by ID
        reshift notes --stats                   # Note statistics
        reshift notes --authors                 # Top note authors
    """
    import json
    import sys

    from .integrations.database.client import (
        is_tunnel_running,
        start_persistent_tunnel,
    )
    from .integrations.notes import get_notes_client

    # Auto-start tunnel if not running
    if not is_tunnel_running():
        console.print("[dim]Starting SSH tunnel...[/]")
        start_persistent_tunnel()

    client = get_notes_client()

    # Read a specific note
    if read:
        data = client.get_note_with_relations(read)
        if not data:
            console.print(f"[red]Note '{read}' not found.[/]")
            return

        note = data["note"]

        if json_output:
            print(
                json.dumps(
                    {
                        "id": note.id,
                        "title": note.title,
                        "type": note.note_type,
                        "source": note.source,
                        "created_at": note.created_at.isoformat(),
                        "created_by": note.created_by_name,
                        "organizations": data["organizations"],
                        "people": data["people"],
                        "notes": note.notes,
                    },
                    indent=2,
                    ensure_ascii=False,
                ),
                file=sys.stdout,
            )
            return

        console.print(f"\n[bold cyan]{note.title or '(Untitled)'}[/]\n")
        console.print(f"[dim]Type:[/] {note.note_type or 'N/A'}")
        console.print(f"[dim]Source:[/] {note.source}")
        console.print(f"[dim]Created:[/] {note.created_at.strftime('%Y-%m-%d %H:%M')}")
        console.print(f"[dim]Author:[/] {note.created_by_name or note.created_by_id}")
        if data["organizations"]:
            console.print(f"[dim]Organizations:[/] {', '.join(data['organizations'])}")
        if data["people"]:
            console.print(f"[dim]People:[/] {', '.join(data['people'])}")
        console.print(f"\n{note.notes}")
        return

    # Show statistics
    if stats:
        s = client.get_stats()

        if json_output:
            print(json.dumps(s, indent=2), file=sys.stdout)
            return

        console.print("\n[bold]Shift Notes Statistics[/]\n")
        console.print(f"Total notes: [cyan]{s['total']:,}[/]")
        console.print(f"Last 30 days: [green]{s['last_30_days']:,}[/]\n")

        table = Table(title="By Type")
        table.add_column("Type", style="cyan")
        table.add_column("Count", justify="right", style="green")
        for t, c in sorted(s["by_type"].items(), key=lambda x: -x[1]):
            if t:
                table.add_row(t, f"{c:,}")
        console.print(table)

        table2 = Table(title="By Source")
        table2.add_column("Source", style="cyan")
        table2.add_column("Count", justify="right", style="green")
        for src, c in s["by_source"].items():
            table2.add_row(src, f"{c:,}")
        console.print(table2)
        return

    # Show top authors
    if authors:
        author_list = client.get_authors(limit=limit)

        if json_output:
            print(json.dumps(author_list, indent=2, default=str), file=sys.stdout)
            return

        table = Table(title="Top Note Authors")
        table.add_column("Name", style="cyan", max_width=25)
        table.add_column("Email", style="dim", max_width=30)
        table.add_column("Notes", justify="right", style="green")

        for a in author_list:
            table.add_row(a["name"] or "", a["email"] or "", f"{a['note_count']:,}")

        console.print(table)
        return

    # Search or list notes
    if org:
        notes_list = client.get_notes_for_organization(org, limit=limit)
        title = f"Notes for '{org}'"
    elif query:
        notes_list = client.search_notes(query, note_type=note_type, limit=limit)
        title = f"Notes matching '{query}'"
    else:
        notes_list = client.list_notes(note_type=note_type, limit=limit)
        title = "Recent Notes" + (f" ({note_type})" if note_type else "")

    if not notes_list:
        console.print("[yellow]No notes found.[/]")
        return

    if json_output:
        print(
            json.dumps(
                [
                    {
                        "id": n.id,
                        "title": n.title,
                        "type": n.note_type,
                        "created_at": n.created_at.isoformat(),
                        "created_by": n.created_by_name,
                        "notes": n.notes if full else n.notes[:200],
                    }
                    for n in notes_list
                ],
                indent=2,
                ensure_ascii=False,
            ),
            file=sys.stdout,
        )
        return

    if full:
        console.print(f"\n[bold]{title}[/]\n")
        for n in notes_list:
            console.print(f"[cyan]{n.title or '(Untitled)'}[/] [{n.note_type or 'N/A'}]")
            created = n.created_at.strftime("%Y-%m-%d")
            author = n.created_by_name or "Unknown"
            console.print(f"[dim]{created} by {author}[/]")
            console.print(f"[dim]ID: {n.id}[/]")
            console.print(n.notes)
            console.print()
        return

    table = Table(title=title)
    table.add_column("Title", style="cyan", max_width=40)
    table.add_column("Type", style="green", max_width=15)
    table.add_column("Date", style="dim", max_width=12)
    table.add_column("Author", style="dim", max_width=15)
    table.add_column("ID", style="dim", max_width=12)

    for n in notes_list:
        title_str = (n.title or n.notes[:40])[:40]
        if len(n.title or n.notes) > 40:
            title_str += "..."
        author = (n.created_by_name or "")[:15]
        table.add_row(
            title_str,
            n.note_type or "",
            n.created_at.strftime("%Y-%m-%d"),
            author,
            n.id[:12] + "...",
        )

    console.print(table)
    console.print("\n[dim]Use --read <ID> to read full note[/]")


@app.command(name="slack-thread")
def slack_thread(
    permalink: str = typer.Argument(..., help="Slack message permalink or 'channel_id:timestamp'"),
    json_output: bool = typer.Option(False, "--json", help="Output as JSON"),
):
    """Fetch and display a full Slack thread.

    Examples:
        reshift slack-thread "https://paradigm-ops.slack.com/archives/C01234567/p1234567890123456"
        reshift slack-thread "C01234567:1234567890.123456"
        reshift slack-thread "https://..." --json
    """
    import json
    import re
    import sys

    from .integrations.slack.client import get_thread_replies

    if permalink.startswith("https://"):
        match = re.search(r"/archives/([A-Z0-9]+)/p(\d+)", permalink)
        if not match:
            console.print("[red]Invalid permalink format[/]")
            return
        channel_id = match.group(1)
        ts_raw = match.group(2)
        thread_ts = f"{ts_raw[:10]}.{ts_raw[10:]}"
    elif ":" in permalink:
        channel_id, thread_ts = permalink.split(":", 1)
    else:
        console.print("[red]Provide a Slack permalink or 'channel_id:timestamp'[/]")
        return

    messages = get_thread_replies(channel_id, thread_ts)

    if not messages:
        console.print("[yellow]No messages found in thread.[/]")
        return

    if json_output:
        print(json.dumps(messages, indent=2, ensure_ascii=False), file=sys.stdout)
        return

    console.print(f"\n[bold]Thread ({len(messages)} messages)[/]\n")
    for i, msg in enumerate(messages):
        prefix = "📌" if i == 0 else "  └"
        user = f"[cyan]@{msg['user']}[/]"
        text = msg["text"].replace("\n", "\n     ")
        console.print(f"{prefix} {user}: {text}\n")


if __name__ == "__main__":
    app()
