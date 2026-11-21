from __future__ import annotations

from pathlib import Path

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload


def ensure_drive_folder(
    creds: Credentials,
    folder_name: str,
    folder_id: str = "",
) -> str:
    """Return existing folder_id or find/create a Drive folder by name."""
    if folder_id:
        return folder_id

    service = build("drive", "v3", credentials=creds)
    query = (
        f"name = '{folder_name}' and "
        "mimeType = 'application/vnd.google-apps.folder' and trashed = false"
    )
    results = service.files().list(q=query, fields="files(id, name)", pageSize=1).execute()
    files = results.get("files", [])
    if files:
        return files[0]["id"]

    metadata = {
        "name": folder_name,
        "mimeType": "application/vnd.google-apps.folder",
    }
    created = service.files().create(body=metadata, fields="id").execute()
    return created["id"]


def upload_file_to_drive(
    creds: Credentials,
    file_path: Path,
    folder_id: str,
    mime_type: str,
) -> tuple[str, str]:
    """Upload a file to Google Drive and return (file_id, webViewLink)."""
    service = build("drive", "v3", credentials=creds)
    file_metadata = {
        "name": file_path.name,
        "parents": [folder_id],
    }
    media = MediaFileUpload(str(file_path), mimetype=mime_type, resumable=True)
    request = service.files().create(
        body=file_metadata,
        media_body=media,
        fields="id, webViewLink",
    )

    response = None
    while response is None:
        _, response = request.next_chunk()

    return response["id"], response.get("webViewLink", "")

