from __future__ import annotations

import io
import json
from pathlib import Path
from typing import Iterable

from google import genai
from google.genai import types
from PIL import Image, ImageDraw, ImageFont

from config import FORMAT_SPECS, HISTORY_FILE, Settings
from src.models import VideoPlan


def _load_history(history_file: Path = HISTORY_FILE) -> list[str]:
    if not history_file.exists():
        return []
    try:
        data = json.loads(history_file.read_text(encoding="utf-8"))
        return [str(item) for item in data if isinstance(item, str)]
    except (json.JSONDecodeError, OSError):
        return []


def record_topic_history(topic: str, history_file: Path = HISTORY_FILE) -> None:
    history_file.parent.mkdir(parents=True, exist_ok=True)
    topics = _load_history(history_file)
    if topic not in topics:
        topics.append(topic)
    history_file.write_text(json.dumps(topics, indent=2), encoding="utf-8")


def _load_font(size: int, bold: bool = True) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    candidates = (
        [
            "C:/Windows/Fonts/COOPBL.TTF",
            "C:/Windows/Fonts/georgiab.ttf",
            "C:/Windows/Fonts/comicbd.ttf",
            "C:/Windows/Fonts/arialbd.ttf",
            "C:/Windows/Fonts/impact.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
            "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
        ]
        if bold
        else [
            "C:/Windows/Fonts/georgia.ttf",
            "C:/Windows/Fonts/arial.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSerif.ttf",
            "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
        ]
    )
    for path in candidates:
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size=size)
            except OSError:
                continue
    return ImageFont.load_default()


def generate_video_plan(
    settings: Settings,
    niche: str,
    video_format: str = "shorts",
    topic: str | None = None,
    past_topics: Iterable[str] | None = None,
    visual_style: str | None = None,
) -> VideoPlan:
    """Use Gemini to generate a viral script, SEO metadata, and visual prompts."""
    if not settings.gemini_api_key or settings.gemini_api_key == "your_gemini_api_key_here":
        raise ValueError("GEMINI_API_KEY is not set. Add it to your .env file.")

    spec = FORMAT_SPECS[video_format]
    avoid_topics = list(past_topics) if past_topics is not None else _load_history()
    avoid_block = (
        f"Avoid repeating these previously covered topics: {', '.join(avoid_topics[-25:])}."
        if avoid_topics
        else ""
    )

    topic_instruction = (
        f"Use this exact topic: '{topic}'."
        if topic
        else (
            f"Pick a single hyper-engaging, surprising, viral-worthy topic in the '{niche}' niche "
            f"(e.g., a counterintuitive psychology effect, a bizarre verified historical event, or a mind-blowing scientific fact)."
        )
    )

    if video_format == "shorts":
        pacing_rules = (
            f"- Target total spoken duration: ~{spec.target_duration_seconds} seconds (110–135 words total across all scenes).\n"
            f"- Create exactly {spec.scene_count} fast-paced scenes.\n"
            "- Scene 1 MUST be a 1-sentence pattern-interrupt hook in the first 3 seconds.\n"
            "- Include #Shorts in hashtags and keep the title under 70 characters with a strong curiosity gap."
        )
    else:
        pacing_rules = (
            f"- Target total spoken duration: ~{spec.target_duration_seconds} seconds (400–520 words total across all scenes).\n"
            f"- Create exactly {spec.scene_count} well-paced storytelling scenes with retention hooks between sections.\n"
            "- Scene 1 MUST open with a compelling mystery or bold claim.\n"
            "- Title should be under 80 characters, high-CTR, and curiosity-driven."
        )

    style = (visual_style or settings.visual_style).lower()
    if style in ("retro_cartoon", "cartoon"):
        visual_direction = (
            "- Every scene's `visual_prompt` and `thumbnail_prompt` MUST follow a 1930s retro rubber-hose 2D cartoon "
            "animation style (classic ink-and-paint aesthetic like Cuphead / Fleischer Studios): bouncy expressive "
            "cartoon characters with pie-cut eyes, white gloves, and bold dark ink outlines, set in a warm vintage "
            "cream, muted teal, sepia, and burnt-amber color palette—NEVER photorealistic, NEVER 3D, and NEVER ask "
            "for text or words inside the image/video."
        )
    else:
        visual_direction = (
            "- Every scene's `visual_prompt` must describe a vivid, cinematic, photorealistic or stylized 3D visual "
            "with lighting, camera angle, and mood—NEVER ask for text or words inside the generated image/video."
        )

    prompt = f"""You are an elite YouTube strategist, viral scriptwriter, and visual director.
Niche: {niche}
Format: {video_format.upper()} ({spec.aspect_ratio})
{topic_instruction}
{avoid_block}

Requirements:
{pacing_rules}
- Narration must sound natural, punchy, and conversational for voiceover (no stage directions, no markdown, no emojis in narration).
{visual_direction}
- `description` must include a 2-line hook, a brief value summary, a subscribe call-to-action, and the hashtags at the bottom.
- `thumbnail_text` must be 2–4 punchy uppercase words (e.g., "THEY LIED TO YOU", "BRAIN TRICK", "FORGOTTEN EMPIRE").
"""

    client = genai.Client(api_key=settings.gemini_api_key)
    response = client.models.generate_content(
        model=settings.gemini_text_model,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_mime_type="application/json",
            response_schema=VideoPlan,
            temperature=0.85,
        ),
    )

    plan = VideoPlan.model_validate_json(response.text)
    if video_format == "shorts" and not any(
        tag.lower() == "#shorts" for tag in plan.hashtags
    ):
        plan.hashtags.insert(0, "#Shorts")
    return plan


def generate_ai_image_bytes(
    client: genai.Client,
    model: str,
    prompt: str,
    aspect_ratio: str,
) -> bytes | None:
    """Generate image bytes using either Imagen (generate_images) or Gemini image models."""
    if model.lower().startswith("imagen"):
        result = client.models.generate_images(
            model=model,
            prompt=prompt,
            config=types.GenerateImagesConfig(
                number_of_images=1,
                aspect_ratio=aspect_ratio,
                output_mime_type="image/jpeg",
            ),
        )
        if result.generated_images:
            return result.generated_images[0].image.image_bytes
        return None

    response = client.models.generate_content(
        model=model,
        contents=prompt,
        config=types.GenerateContentConfig(
            response_modalities=["IMAGE"],
            image_config=types.ImageConfig(aspect_ratio=aspect_ratio),
        ),
    )
    for candidate in response.candidates or []:
        if not candidate.content or not candidate.content.parts:
            continue
        for part in candidate.content.parts:
            if part.inline_data and part.inline_data.data:
                return part.inline_data.data
    return None


def generate_thumbnail(
    settings: Settings,
    plan: VideoPlan,
    output_path: Path,
) -> Path:
    """Generate a high-CTR 1280x720 thumbnail with Gemini/Imagen + bold text overlay."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    img: Image.Image | None = None

    if settings.gemini_api_key and settings.gemini_api_key != "your_gemini_api_key_here":
        try:
            client = genai.Client(api_key=settings.gemini_api_key)
            style_suffix = (
                "Classic 1930s retro rubber-hose 2D cartoon animation style, pie-cut eyes, white gloves, bold dark ink "
                "outlines, warm vintage cream and muted teal ink-and-paint palette, no text, no letters, no watermarks."
                if settings.visual_style.lower() in ("retro_cartoon", "cartoon")
                else "High contrast, dramatic cinematic lighting, vibrant colors, clean focal subject, no text, no letters, no watermarks."
            )
            raw_bytes = generate_ai_image_bytes(
                client=client,
                model=settings.gemini_image_model,
                prompt=f"{plan.thumbnail_prompt}. {style_suffix}",
                aspect_ratio="16:9",
            )
            if raw_bytes:
                img = Image.open(io.BytesIO(raw_bytes)).convert("RGB")
        except Exception as exc:
            print(f"[thumbnail] Image generation failed, using gradient fallback: {exc}")

    if img is None:
        img = _create_gradient_background(1280, 720, (18, 22, 46), (130, 28, 72))

    img = img.resize((1280, 720), Image.Resampling.LANCZOS)
    img = _overlay_thumbnail_text(img, plan.thumbnail_text)
    img.save(output_path, format="JPEG", quality=95)
    return output_path


def _create_gradient_background(
    width: int,
    height: int,
    top_color: tuple[int, int, int],
    bottom_color: tuple[int, int, int],
) -> Image.Image:
    base = Image.new("RGB", (width, height), top_color)
    draw = ImageDraw.Draw(base)
    for y in range(height):
        ratio = y / max(height - 1, 1)
        r = int(top_color[0] + (bottom_color[0] - top_color[0]) * ratio)
        g = int(top_color[1] + (bottom_color[1] - top_color[1]) * ratio)
        b = int(top_color[2] + (bottom_color[2] - top_color[2]) * ratio)
        draw.line([(0, y), (width, y)], fill=(r, g, b))
    return base


def _overlay_thumbnail_text(img: Image.Image, text: str) -> Image.Image:
    """Add dark vignette and bold high-contrast headline text to the thumbnail."""
    rgba = img.convert("RGBA")
    overlay = Image.new("RGBA", rgba.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)

    # Bottom gradient scrim for readability
    w, h = rgba.size
    for y in range(h // 2, h):
        alpha = int(190 * ((y - h // 2) / max(h // 2, 1)))
        draw.line([(0, y), (w, y)], fill=(0, 0, 0, alpha))

    composited = Image.alpha_composite(rgba, overlay)
    text_draw = ImageDraw.Draw(composited)

    headline = (text or "MIND BLOWN").upper().strip()
    words = headline.split()
    if len(words) > 2:
        mid = len(words) // 2
        lines = [" ".join(words[:mid]), " ".join(words[mid:])]
    else:
        lines = [headline]

    font = _load_font(size=104, bold=True)
    line_heights = []
    line_widths = []
    for line in lines:
        bbox = text_draw.textbbox((0, 0), line, font=font, stroke_width=6)
        line_widths.append(bbox[2] - bbox[0])
        line_heights.append(bbox[3] - bbox[1])

    total_height = sum(line_heights) + (len(lines) - 1) * 18
    current_y = h - total_height - 55

    for idx, line in enumerate(lines):
        lw = line_widths[idx]
        x = (w - lw) // 2
        fill_color = (255, 244, 214, 255) if idx == 0 else (242, 184, 75, 255)
        text_draw.text(
            (x, current_y),
            line,
            font=font,
            fill=fill_color,
            stroke_width=9,
            stroke_fill=(30, 27, 24, 255),
        )
        current_y += line_heights[idx] + 18

    return composited.convert("RGB")

