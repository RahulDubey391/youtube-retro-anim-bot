from __future__ import annotations

from pathlib import Path

from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build
from googleapiclient.http import MediaFileUpload

from src.models import VideoPlan


def _format_description(plan: VideoPlan) -> str:
    hashtags_line = " ".join(
        tag if tag.startswith("#") else f"#{tag}" for tag in plan.hashtags
    )
    desc = plan.description.strip()
    if hashtags_line and hashtags_line.lower() not in desc.lower():
        desc = f"{desc}\n\n{hashtags_line}"
    return desc[:4900]


def upload_to_youtube(
    creds: Credentials,
    video_path: Path,
    thumbnail_path: Path | None,
    plan: VideoPlan,
    privacy_status: str = "private",
    category_id: str = "27",
) -> tuple[str, str]:
    """Upload video + metadata + custom thumbnail to YouTube and return (video_id, url)."""
    youtube = build("youtube", "v3", credentials=creds)

    title = plan.title.strip()[:100]
    if plan.video_format == "shorts" and "#shorts" not in title.lower():
        candidate = f"{title} #Shorts"
        if len(candidate) <= 100:
            title = candidate

    body = {
        "snippet": {
            "title": title,
            "description": _format_description(plan),
            "tags": [t.lstrip("#") for t in plan.tags[:20]],
            "categoryId": category_id,
        },
        "status": {
            "privacyStatus": privacy_status,
            "selfDeclaredMadeForKids": False,
        },
    }

    media = MediaFileUpload(
        str(video_path),
        mimetype="video/mp4",
        chunksize=8 * 1024 * 1024,
        resumable=True,
    )
    request = youtube.videos().insert(
        part="snippet,status",
        body=body,
        media_body=media,
    )

    response = None
    while response is None:
        _, response = request.next_chunk()

    video_id = response["id"]

    if thumbnail_path and thumbnail_path.exists():
        try:
            thumb_media = MediaFileUpload(str(thumbnail_path), mimetype="image/jpeg")
            youtube.thumbnails().set(
                videoId=video_id,
                media_body=thumb_media,
            ).execute()
        except Exception as exc:
            print(
                f"[youtube] Thumbnail upload skipped/failed (channel may need phone verification): {exc}"
            )

    url = (
        f"https://youtube.com/shorts/{video_id}"
        if plan.video_format == "shorts"
        else f"https://www.youtube.com/watch?v={video_id}"
    )
    return video_id, url

