from __future__ import annotations

from pathlib import Path

from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow

YOUTUBE_SCOPES = ["https://www.googleapis.com/auth/youtube"]
DRIVE_SCOPES = ["https://www.googleapis.com/auth/drive.file"]


def get_google_credentials(
    client_secrets_path: str | Path,
    token_path: str | Path,
    scopes: list[str] | None = None,
) -> Credentials:
    """Authenticate via OAuth 2.0 and cache refreshable credentials in token_path."""
    secrets_file = Path(client_secrets_path)
    token_file = Path(token_path)
    target_scopes = scopes or YOUTUBE_SCOPES

    creds: Credentials | None = None
    if token_file.exists():
        creds = Credentials.from_authorized_user_file(str(token_file), target_scopes)

    if creds and creds.expired and creds.refresh_token:
        creds.refresh(Request())
        token_file.write_text(creds.to_json(), encoding="utf-8")
        return creds

    if creds and creds.valid:
        return creds

    if not secrets_file.exists():
        raise FileNotFoundError(
            f"Google OAuth client secrets file not found at '{secrets_file}'. "
            "Download it from Google Cloud Console (OAuth 2.0 Client ID -> Desktop App)."
        )

    flow = InstalledAppFlow.from_client_secrets_file(str(secrets_file), target_scopes)
    creds = flow.run_local_server(port=0)
    token_file.write_text(creds.to_json(), encoding="utf-8")
    return creds
