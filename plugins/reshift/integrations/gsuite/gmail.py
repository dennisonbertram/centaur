"""Gmail API client."""

from googleapiclient.discovery import build

from .auth import get_credentials


def get_gmail_service():
    """Get authenticated Gmail service."""
    creds = get_credentials()
    if not creds:
        raise RuntimeError("Not authenticated. Run `reshift auth` first.")
    return build("gmail", "v1", credentials=creds)


def search_emails(query: str, max_results: int = 10) -> list[dict]:
    """Search emails matching query."""
    service = get_gmail_service()

    results = (
        service.users().messages().list(userId="me", q=query, maxResults=max_results).execute()
    )

    messages = results.get("messages", [])
    emails = []

    for msg in messages:
        full = service.users().messages().get(userId="me", id=msg["id"]).execute()
        headers = {h["name"]: h["value"] for h in full["payload"]["headers"]}
        emails.append(
            {
                "id": msg["id"],
                "subject": headers.get("Subject", ""),
                "from": headers.get("From", ""),
                "date": headers.get("Date", ""),
                "snippet": full.get("snippet", ""),
            }
        )

    return emails


def get_email_body(message_id: str) -> str:
    """Get full email body."""
    import base64

    service = get_gmail_service()
    message = service.users().messages().get(userId="me", id=message_id, format="full").execute()

    def extract_body(payload):
        if "body" in payload and payload["body"].get("data"):
            return base64.urlsafe_b64decode(payload["body"]["data"]).decode("utf-8")
        if "parts" in payload:
            for part in payload["parts"]:
                if part["mimeType"] == "text/plain":
                    if part["body"].get("data"):
                        return base64.urlsafe_b64decode(part["body"]["data"]).decode("utf-8")
                result = extract_body(part)
                if result:
                    return result
        return ""

    return extract_body(message["payload"])
