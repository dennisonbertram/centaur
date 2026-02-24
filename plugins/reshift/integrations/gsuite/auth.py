"""Google OAuth authentication flow."""

from pathlib import Path

from dotenv import load_dotenv
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from rich.console import Console

load_dotenv()

# Scopes for Gmail, Calendar, and Drive
SCOPES = [
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/calendar",  # Full access for create/edit
    "https://www.googleapis.com/auth/drive.readonly",
]

TOKEN_PATH = Path.home() / ".reshift" / "token.json"
CREDENTIALS_PATH = Path.home() / ".reshift" / "credentials.json"


def get_credentials() -> Credentials | None:
    """Get valid credentials, refreshing if necessary."""
    creds = None

    if TOKEN_PATH.exists():
        creds = Credentials.from_authorized_user_file(str(TOKEN_PATH), SCOPES)

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        _save_token(creds)

    return creds


def _save_token(creds: Credentials):
    """Save credentials to token file."""
    TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    TOKEN_PATH.write_text(creds.to_json())


def authenticate():
    """Run OAuth flow to authenticate with Google."""
    console = Console()

    creds = get_credentials()
    if creds and creds.valid:
        console.print("[green]Already authenticated with Google![/]")
        return creds

    if not CREDENTIALS_PATH.exists():
        console.print(
            f"[red]No credentials.json found at {CREDENTIALS_PATH}[/]\n"
            "\n"
            "To set up Google OAuth:\n"
            "1. Go to https://console.cloud.google.com/apis/credentials\n"
            "2. Create OAuth 2.0 Client ID (Desktop app)\n"
            "3. Download JSON and save to ~/.reshift/credentials.json\n"
        )
        return None

    console.print("[yellow]Opening browser for Google authentication...[/]")

    flow = InstalledAppFlow.from_client_secrets_file(str(CREDENTIALS_PATH), SCOPES)
    creds = flow.run_local_server(port=0)

    _save_token(creds)
    console.print("[green]Successfully authenticated with Google![/]")

    return creds
