from __future__ import annotations

import argparse
import re
from datetime import datetime
from pathlib import Path

from config import OUTPUT_DIR, get_settings
from src.drive_uploader import ensure_drive_folder, upload_file_to_drive
from src.gemini_content import (
    generate_thumbnail,
    generate_video_plan,
    record_topic_history,
)
from src.google_auth import DRIVE_SCOPES, YOUTUBE_SCOPES, get_google_credentials
from src.media_generator import generate_scene_media, generate_voiceover
from src.models import UploadResult
from src.video_assembler import assemble_video
from src.youtube_uploader import upload_to_youtube


def _slugify(value: str) -> str:
    cleaned = re.sub(r"[^a-zA-Z0-9]+", "-", value.lower()).strip("-")
    return cleaned[:48] or "video"


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Automate YouTube Shorts & Long-Form video creation using Gemini, Drive & YouTube APIs."
    )
    parser.add_argument(
        "--format",
        choices=["shorts", "long"],
        default=None,
        help="Video format: 'shorts' (9:16) or 'long' (16:9).",
    )
    parser.add_argument(
        "--style",
        choices=["retro_cartoon", "cartoon", "realistic"],
        default=None,
        help="Visual art style: 'retro_cartoon' (default) or 'realistic'.",
    )
    parser.add_argument(
        "--niche",
        type=str,
        default=None,
        help="Target niche (default from .env).",
    )
    parser.add_argument(
        "--topic",
        type=str,
        default=None,
        help="Optional specific topic override; otherwise Gemini chooses a viral topic.",
    )
    parser.add_argument(
        "--use-veo",
        action=argparse.BooleanOptionalAction,
        default=None,
        help="Use Gemini Veo for video clips with auto-fallback to Imagen.",
    )
    parser.add_argument(
        "--upload-drive",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Upload generated video, thumbnail, and metadata to Google Drive.",
    )
    parser.add_argument(
        "--upload-youtube",
        action=argparse.BooleanOptionalAction,
        default=True,
        help="Upload generated video and thumbnail to YouTube.",
    )
    parser.add_argument(
        "--privacy",
        choices=["private", "unlisted", "public"],
        default=None,
        help="YouTube privacy status (default from .env, usually 'private').",
    )
    parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Generate video, thumbnail, and metadata locally without uploading to Drive or YouTube.",
    )
    return parser.parse_args()


def main() -> None:
    args = parse_args()
    settings = get_settings()

    video_format = args.format or settings.default_format
    niche = args.niche or settings.default_niche
    privacy = args.privacy or settings.youtube_privacy_status
    if args.style:
        settings.visual_style = args.style

    print(
        f"[1/5] Generating viral {video_format.upper()} ({settings.visual_style}) plan in niche: {niche}"
    )
    plan = generate_video_plan(
        settings=settings,
        niche=niche,
        video_format=video_format,
        topic=args.topic,
        visual_style=settings.visual_style,
    )

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    run_dir = OUTPUT_DIR / f"{timestamp}_{_slugify(plan.topic)}"
    run_dir.mkdir(parents=True, exist_ok=True)

    plan_path = run_dir / "metadata.json"
    plan_path.write_text(plan.model_dump_json(indent=2), encoding="utf-8")
    print(f"      Topic: {plan.topic}")
    print(f"      Title: {plan.title}")

    print("[2/5] Generating voiceover & word timings...")
    full_narration = " ".join(scene.narration.strip() for scene in plan.scenes)
    audio_path = run_dir / "voiceover.mp3"
    word_timings = generate_voiceover(
        text=full_narration,
        voice=settings.tts_voice,
        audio_path=audio_path,
    )

    print("[3/5] Generating scene visuals (Veo with Imagen fallback) & thumbnail...")
    media_paths = generate_scene_media(
        settings=settings,
        scenes=plan.scenes,
        video_format=video_format,
        assets_dir=run_dir / "assets",
        use_veo=args.use_veo,
    )
    thumbnail_path = generate_thumbnail(
        settings=settings,
        plan=plan,
        output_path=run_dir / "thumbnail.jpg",
    )

    print("[4/5] Assembling final video with animated captions...")
    video_path = assemble_video(
        media_paths=media_paths,
        audio_path=audio_path,
        word_timings=word_timings,
        video_format=video_format,
        output_path=run_dir / "video.mp4",
        scenes=plan.scenes,
    )
    record_topic_history(plan.topic)
    print(f"      Saved video: {video_path}")
    print(f"      Saved thumbnail: {thumbnail_path}")

    if args.dry_run or (not args.upload_drive and not args.upload_youtube):
        print("[5/5] Skipping uploads (--dry-run or uploads disabled).")
        return

    print("[5/5] Authenticating with Google & uploading...")
    token_base = Path(settings.google_token_file)
    result = UploadResult()

    if args.upload_drive:
        drive_token = token_base.with_name(f"{token_base.stem}_drive{token_base.suffix}")
        drive_creds = get_google_credentials(
            settings.google_client_secrets,
            drive_token,
            DRIVE_SCOPES,
        )
        folder_id = ensure_drive_folder(
            drive_creds,
            settings.google_drive_folder_name,
            settings.google_drive_folder_id,
        )
        result.drive_folder_id = folder_id
        vid_id, vid_url = upload_file_to_drive(drive_creds, video_path, folder_id, "video/mp4")
        _, thumb_url = upload_file_to_drive(drive_creds, thumbnail_path, folder_id, "image/jpeg")
        upload_file_to_drive(drive_creds, plan_path, folder_id, "application/json")
        result.drive_video_id = vid_id
        result.drive_video_url = vid_url
        result.drive_thumbnail_url = thumb_url
        print(f"      Google Drive video: {vid_url}")

    if args.upload_youtube:
        yt_token = token_base.with_name(f"{token_base.stem}_youtube{token_base.suffix}")
        yt_creds = get_google_credentials(
            settings.google_client_secrets,
            yt_token,
            YOUTUBE_SCOPES,
        )
        yt_id, yt_url = upload_to_youtube(
            creds=yt_creds,
            video_path=video_path,
            thumbnail_path=thumbnail_path,
            plan=plan,
            privacy_status=privacy,
            category_id=settings.youtube_category_id,
        )
        result.youtube_video_id = yt_id
        result.youtube_url = yt_url
        print(f"      YouTube URL ({privacy}): {yt_url}")

    (run_dir / "upload_result.json").write_text(
        result.model_dump_json(indent=2), encoding="utf-8"
    )


if __name__ == "__main__":
    main()

