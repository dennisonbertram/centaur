"""Google Drive API client."""

import io

from googleapiclient.discovery import build
from googleapiclient.http import MediaIoBaseDownload

from .auth import get_credentials


def get_drive_service():
    """Get authenticated Drive service."""
    creds = get_credentials()
    if not creds:
        raise RuntimeError("Not authenticated. Run `reshift auth` first.")
    return build("drive", "v3", credentials=creds)


def search_files(query: str, max_results: int = 20) -> list[dict]:
    """Search Drive files by name or content."""
    service = get_drive_service()

    # Search in file name and full text
    drive_query = f"(name contains '{query}' or fullText contains '{query}') and trashed = false"

    results = (
        service.files()
        .list(
            q=drive_query,
            pageSize=max_results,
            fields="files(id, name, mimeType, modifiedTime, webViewLink, owners)",
        )
        .execute()
    )

    return [
        {
            "id": f["id"],
            "name": f["name"],
            "mimeType": f["mimeType"],
            "modifiedTime": f["modifiedTime"],
            "link": f.get("webViewLink", ""),
            "owner": f["owners"][0]["emailAddress"] if f.get("owners") else "",
        }
        for f in results.get("files", [])
    ]


def get_file_content(file_id: str) -> str:
    """Get text content of a Drive file."""
    service = get_drive_service()

    # Get file metadata
    file_meta = service.files().get(fileId=file_id, fields="mimeType,name").execute()
    mime_type = file_meta["mimeType"]

    # Handle Google Docs - export as plain text
    if mime_type == "application/vnd.google-apps.document":
        content = service.files().export(fileId=file_id, mimeType="text/plain").execute()
        return content.decode("utf-8")

    # Handle Google Sheets - export as CSV
    if mime_type == "application/vnd.google-apps.spreadsheet":
        content = service.files().export(fileId=file_id, mimeType="text/csv").execute()
        return content.decode("utf-8")

    # Handle regular files - download directly
    if mime_type.startswith("text/") or mime_type == "application/json":
        request = service.files().get_media(fileId=file_id)
        buffer = io.BytesIO()
        downloader = MediaIoBaseDownload(buffer, request)
        done = False
        while not done:
            _, done = downloader.next_chunk()
        return buffer.getvalue().decode("utf-8")

    return f"[Cannot extract text from {mime_type}]"


def list_folder(folder_id: str = "root", max_results: int = 50) -> list[dict]:
    """List files in a Drive folder."""
    service = get_drive_service()

    results = (
        service.files()
        .list(
            q=f"'{folder_id}' in parents and trashed = false",
            pageSize=max_results,
            fields="files(id, name, mimeType, modifiedTime)",
            orderBy="modifiedTime desc",
        )
        .execute()
    )

    return results.get("files", [])
