from __future__ import annotations

import asyncio
import io
import time
from pathlib import Path

import edge_tts
from google import genai
from google.genai import types
from PIL import Image, ImageDraw

from config import FORMAT_SPECS, Settings
from src.gemini_content import generate_ai_image_bytes
from src.models import Scene, WordTiming


async def _synthesize_tts_async(
    text: str,
    voice: str,
    audio_path: Path,
) -> list[WordTiming]:
    fallback_voices = [voice, "en-US-GuyNeural", "en-US-JennyNeural"]
    last_exc: Exception | None = None

    for candidate_voice in dict.fromkeys(fallback_voices):
        for attempt in range(3):
            try:
                communicate = edge_tts.Communicate(text, candidate_voice)
                timings: list[WordTiming] = []
                audio_chunks = bytearray()

                async for chunk in communicate.stream():
                    if chunk["type"] == "audio":
                        audio_chunks.extend(chunk["data"])
                    elif chunk["type"] == "WordBoundary":
                        start_sec = chunk["offset"] / 10_000_000.0
                        dur_sec = chunk["duration"] / 10_000_000.0
                        timings.append(
                            WordTiming(
                                text=chunk["text"],
                                start=start_sec,
                                end=start_sec + max(dur_sec, 0.12),
                            )
                        )

                if audio_chunks:
                    audio_path.parent.mkdir(parents=True, exist_ok=True)
                    audio_path.write_bytes(bytes(audio_chunks))
                    return timings
            except Exception as exc:
                last_exc = exc
                await asyncio.sleep(1.5 * (attempt + 1))

    raise RuntimeError(f"TTS synthesis failed after retries: {last_exc}")


def generate_voiceover(
    text: str,
    voice: str,
    audio_path: Path,
) -> list[WordTiming]:
    """Generate MP3 voiceover and word-level subtitle timings via edge-tts."""
    return asyncio.run(_synthesize_tts_async(text, voice, audio_path))


def _get_veo_client(settings: Settings, fallback_client: genai.Client) -> genai.Client:
    if settings.use_vertexai_veo:
        project = settings.google_cloud_project or None
        if not project:
            try:
                import google.auth

                _, project = google.auth.default()
            except Exception:
                project = None
        if project:
            return genai.Client(
                vertexai=True,
                project=project,
                location=settings.google_cloud_location or "us-central1",
            )
    return fallback_client


def generate_scene_media(
    settings: Settings,
    scenes: list[Scene],
    video_format: str,
    assets_dir: Path,
    use_veo: bool | None = None,
) -> list[Path]:
    """Generate a video clip (Veo) or fallback image (Imagen/Gemini) for each scene."""
    assets_dir.mkdir(parents=True, exist_ok=True)
    spec = FORMAT_SPECS[video_format]
    try_veo = settings.use_veo if use_veo is None else use_veo
    veo_available = try_veo and (settings.use_vertexai_veo or bool(settings.gemini_api_key))

    client = genai.Client(api_key=settings.gemini_api_key)
    veo_client = _get_veo_client(settings, client) if veo_available else client
    media_paths: list[Path] = []

    for scene in scenes:
        if veo_available:
            veo_path = assets_dir / f"scene_{scene.scene_number:02d}.mp4"
            try:
                _generate_veo_clip(
                    client=veo_client,
                    model=settings.gemini_veo_model,
                    prompt=scene.visual_prompt,
                    aspect_ratio=spec.aspect_ratio,
                    output_path=veo_path,
                    visual_style=settings.visual_style,
                )
                media_paths.append(veo_path)
                continue
            except Exception as exc:
                print(
                    f"[veo] Scene {scene.scene_number} Veo failed ({exc}); "
                    "falling back to image + cartoon animation."
                )
                # Disable Veo for remaining scenes if it's an auth/quota/model error
                veo_available = False

        img_path = assets_dir / f"scene_{scene.scene_number:02d}.jpg"
        _generate_scene_image(
            client=client,
            model=settings.gemini_image_model,
            prompt=scene.visual_prompt,
            aspect_ratio=spec.aspect_ratio,
            width=spec.width,
            height=spec.height,
            output_path=img_path,
            visual_style=settings.visual_style,
        )
        media_paths.append(img_path)

    return media_paths


def _style_prompt_suffix(visual_style: str) -> str:
    if visual_style.lower() in ("retro_cartoon", "cartoon"):
        return (
            "Classic 1930s retro rubber-hose 2D cartoon animation style, bouncy ink-and-paint characters with "
            "pie-cut eyes and white gloves, bold dark ink outlines, warm vintage cream and muted teal palette, "
            "smooth classic hand-drawn animation motion, no text, no watermarks."
        )
    return "Photorealistic, dramatic cinematic lighting, no text, no watermarks."


def _generate_veo_clip(
    client: genai.Client,
    model: str,
    prompt: str,
    aspect_ratio: str,
    output_path: Path,
    visual_style: str = "cartoon",
) -> Path:
    duration_seconds = 6 if aspect_ratio == "9:16" else 8
    operation = client.models.generate_videos(
        model=model,
        prompt=f"{prompt}. Smooth animated camera movement. {_style_prompt_suffix(visual_style)}",
        config=types.GenerateVideosConfig(
            aspect_ratio=aspect_ratio,
            number_of_videos=1,
            duration_seconds=duration_seconds,
        ),
    )

    deadline = time.monotonic() + 300
    while not operation.done:
        if time.monotonic() > deadline:
            raise TimeoutError("Veo generation timed out after 300 seconds.")
        time.sleep(10)
        operation = client.operations.get(operation)

    if not operation.response or not operation.response.generated_videos:
        raise RuntimeError("Veo returned no generated videos.")

    generated_video = operation.response.generated_videos[0]
    if getattr(generated_video.video, "video_bytes", None):
        output_path.write_bytes(generated_video.video.video_bytes)
    else:
        client.files.download(file=generated_video.video)
        generated_video.video.save(str(output_path))
    return output_path


def _generate_scene_image(
    client: genai.Client,
    model: str,
    prompt: str,
    aspect_ratio: str,
    width: int,
    height: int,
    output_path: Path,
    visual_style: str = "cartoon",
) -> Path:
    try:
        raw = generate_ai_image_bytes(
            client=client,
            model=model,
            prompt=f"{prompt}. {_style_prompt_suffix(visual_style)}",
            aspect_ratio=aspect_ratio,
        )
        if raw:
            img = Image.open(io.BytesIO(raw)).convert("RGB")
            img = img.resize((width, height), Image.Resampling.LANCZOS)
            img.save(output_path, format="JPEG", quality=92)
            return output_path
    except Exception as exc:
        print(f"[image] Image generation failed ({exc}); using stylized fallback.")

    fallback = Image.new("RGB", (width, height), (20, 26, 48))
    draw = ImageDraw.Draw(fallback)
    for y in range(height):
        shade = int(20 + 45 * (y / max(height - 1, 1)))
        draw.line([(0, y), (width, y)], fill=(shade, 26, 65))
    fallback.save(output_path, format="JPEG", quality=90)
    return output_path

