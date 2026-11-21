from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
OUTPUT_DIR = BASE_DIR / "output"
HISTORY_FILE = OUTPUT_DIR / "history.json"


@dataclass(frozen=True)
class VideoFormatSpec:
    name: str
    width: int
    height: int
    aspect_ratio: str
    target_duration_seconds: int
    scene_count: int


FORMAT_SPECS: dict[str, VideoFormatSpec] = {
    "shorts": VideoFormatSpec(
        name="shorts",
        width=1080,
        height=1920,
        aspect_ratio="9:16",
        target_duration_seconds=50,
        scene_count=6,
    ),
    "long": VideoFormatSpec(
        name="long",
        width=1920,
        height=1080,
        aspect_ratio="16:9",
        target_duration_seconds=180,
        scene_count=12,
    ),
}


@dataclass
class Settings:
    gemini_api_key: str = os.getenv("GEMINI_API_KEY", "")
    gemini_text_model: str = os.getenv("GEMINI_TEXT_MODEL", "gemini-3.8-flash")
    gemini_image_model: str = os.getenv("GEMINI_IMAGE_MODEL", "gemini-3.1-flash-image")
    gemini_veo_model: str = os.getenv("GEMINI_VEO_MODEL", "veo-3.1-fast-generate-001")
    use_veo: bool = os.getenv("USE_VEO", "true").lower() in ("1", "true", "yes")
    use_vertexai_veo: bool = os.getenv("USE_VERTEXAI_VEO", "true").lower() in ("1", "true", "yes")
    google_cloud_project: str = os.getenv("GOOGLE_CLOUD_PROJECT", "")
    google_cloud_location: str = os.getenv("GOOGLE_CLOUD_LOCATION", "us-central1")

    default_niche: str = os.getenv(
        "DEFAULT_NICHE", "Mind-Blowing Facts, Psychology & History"
    )
    default_format: str = os.getenv("DEFAULT_FORMAT", "shorts")
    visual_style: str = os.getenv("VISUAL_STYLE", "retro_cartoon")
    tts_voice: str = os.getenv("TTS_VOICE", "en-US-AndrewMultilingualNeural")

    google_client_secrets: str = os.getenv("GOOGLE_CLIENT_SECRETS", "client_secrets.json")
    google_token_file: str = os.getenv("GOOGLE_TOKEN_FILE", "token.json")
    google_drive_folder_name: str = os.getenv(
        "GOOGLE_DRIVE_FOLDER_NAME", "YouTube Automation Videos"
    )
    google_drive_folder_id: str = os.getenv("GOOGLE_DRIVE_FOLDER_ID", "")

    youtube_privacy_status: str = os.getenv("YOUTUBE_PRIVACY_STATUS", "private")
    youtube_category_id: str = os.getenv("YOUTUBE_CATEGORY_ID", "27")


def get_settings() -> Settings:
    return Settings()

