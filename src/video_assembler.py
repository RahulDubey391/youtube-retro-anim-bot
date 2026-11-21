from __future__ import annotations

from pathlib import Path

import numpy as np
from moviepy import (
    AudioFileClip,
    CompositeVideoClip,
    ImageClip,
    VideoClip,
    VideoFileClip,
    concatenate_videoclips,
    vfx,
)
from PIL import Image, ImageDraw, ImageFont

from config import FORMAT_SPECS
from src.models import Scene, WordTiming


def _load_caption_font(size: int) -> ImageFont.FreeTypeFont | ImageFont.ImageFont:
    """Load a bold 1930s retro-cartoon display font with cross-platform fallbacks."""
    for path in (
        "C:/Windows/Fonts/COOPBL.TTF",
        "C:/Windows/Fonts/georgiab.ttf",
        "C:/Windows/Fonts/comicbd.ttf",
        "C:/Windows/Fonts/arialbd.ttf",
        "C:/Windows/Fonts/impact.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSerif-Bold.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    ):
        if Path(path).exists():
            try:
                return ImageFont.truetype(path, size=size)
            except OSError:
                continue
    return ImageFont.load_default()


def _group_words_into_captions(
    timings: list[WordTiming],
    words_per_chunk: int = 3,
) -> list[tuple[str, float, float]]:
    if not timings:
        return []
    chunks: list[tuple[str, float, float]] = []
    for i in range(0, len(timings), words_per_chunk):
        group = timings[i : i + words_per_chunk]
        text = " ".join(w.text for w in group).upper()
        start = group[0].start
        end = max(group[-1].end, start + 0.25)
        chunks.append((text, start, end))
    return chunks


def _render_caption_frame(
    text: str,
    width: int,
    height: int,
    font_size: int,
) -> np.ndarray:
    """Render embedded 1930s retro-cartoon subtitles (vintage cream & dark ink)."""
    canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    draw = ImageDraw.Draw(canvas)
    font = _load_caption_font(font_size)

    bbox = draw.textbbox((0, 0), text, font=font, stroke_width=6)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]
    x = max((width - tw) // 2, 20)
    y = int(height * 0.74) if height > width else int(height * 0.80)

    pad_x, pad_y = 28, 14
    draw.rounded_rectangle(
        [x - pad_x, y - pad_y, x + tw + pad_x, y + th + pad_y],
        radius=20,
        fill=(31, 42, 48, 215),
        outline=(255, 244, 214, 245),
        width=4,
    )
    draw.text(
        (x, y),
        text,
        font=font,
        fill=(255, 244, 214, 255),
        stroke_width=6,
        stroke_fill=(30, 27, 24, 255),
    )
    return np.array(canvas)


def _render_hook_badge_image(
    text: str,
    width: int,
    is_shorts: bool,
) -> Image.Image:
    """Render a 1930s retro-cartoon callout badge for spring pop-in animation."""
    font = _load_caption_font(42 if is_shorts else 36)
    label = text.upper().strip()
    dummy = Image.new("RGBA", (10, 10))
    draw = ImageDraw.Draw(dummy)
    bbox = draw.textbbox((0, 0), label, font=font, stroke_width=4)
    tw = bbox[2] - bbox[0]
    th = bbox[3] - bbox[1]

    pad_x, pad_y = 28, 14
    bw = min(tw + pad_x * 2 + 12, width - 40)
    bh = th + pad_y * 2 + 12
    badge = Image.new("RGBA", (bw, bh), (0, 0, 0, 0))
    bdraw = ImageDraw.Draw(badge)

    bdraw.rounded_rectangle(
        [4, 4, bw - 4, bh - 4],
        radius=20,
        fill=(217, 107, 67, 238),
        outline=(255, 244, 214, 245),
        width=4,
    )
    tx = max((bw - tw) // 2, 8)
    ty = max((bh - th) // 2 - 4, 4)
    bdraw.text(
        (tx, ty),
        label,
        font=font,
        fill=(255, 244, 214, 255),
        stroke_width=4,
        stroke_fill=(30, 27, 24, 255),
    )
    return badge


def _make_spring_hook_clip(
    text: str,
    start: float,
    duration: float,
    width: int,
    height: int,
    is_shorts: bool,
) -> VideoClip:
    """Animate the scene hook badge with a cartoon spring pop-in."""
    badge = _render_hook_badge_image(text, width, is_shorts)
    bw, bh = badge.size
    target_y = int(height * 0.08) if is_shorts else int(height * 0.06)

    def make_frame(t: float) -> np.ndarray:
        canvas = Image.new("RGBA", (width, height), (0, 0, 0, 0))
        if t < 0.28:
            p = t / 0.28
            scale = 0.25 + 0.87 * np.sin(p * np.pi * 0.68) / np.sin(np.pi * 0.68)
        else:
            scale = 1.0 + 0.02 * np.sin(2.0 * np.pi * (t - 0.28) * 1.4)

        sw = max(int(bw * scale), 10)
        sh = max(int(bh * scale), 10)
        scaled = badge.resize((sw, sh), Image.Resampling.BILINEAR)
        px = (width - sw) // 2
        py = target_y + int(4 * np.sin(2.0 * np.pi * t * 1.4))
        canvas.paste(scaled, (px, py), scaled)
        return np.array(canvas)

    return VideoClip(make_frame, duration=duration).with_start(start)


def _fit_clip_to_duration(clip, target_duration: float):
    if clip.duration >= target_duration:
        return clip.subclipped(0, target_duration)
    loops = int(np.ceil(target_duration / max(clip.duration, 0.1)))
    return concatenate_videoclips([clip] * loops, method="compose").subclipped(
        0, target_duration
    )


def _make_animated_cartoon_clip(
    image_path: Path,
    duration: float,
    width: int,
    height: int,
    scene_index: int = 0,
) -> VideoClip:
    """Animate a fallback cartoon illustration with smooth oversampled pan, zoom, and float."""
    oversample = 1.24
    big_w = int(width * oversample)
    big_h = int(height * oversample)
    pil_img = Image.open(image_path).convert("RGB").resize(
        (big_w, big_h), Image.Resampling.LANCZOS
    )
    src = np.array(pil_img)

    mode = scene_index % 4
    max_dx = big_w - width
    max_dy = big_h - height

    def make_frame(t: float) -> np.ndarray:
        p = min(max(t / max(duration, 0.1), 0.0), 1.0)
        ease = 0.5 - 0.5 * np.cos(np.pi * p)
        bob_y = 0.08 * np.sin(2.0 * np.pi * t * 0.6)

        if mode == 0:
            scale = 1.0 + 0.16 * ease
            x_frac = 0.25 + 0.55 * ease
            y_frac = 0.45 + bob_y
        elif mode == 1:
            scale = 1.16 - 0.16 * ease
            x_frac = 0.80 - 0.55 * ease
            y_frac = 0.50 + bob_y
        elif mode == 2:
            scale = 1.02 + 0.14 * ease
            x_frac = 0.50 + 0.15 * np.sin(np.pi * p)
            y_frac = 0.80 - 0.55 * ease
        else:
            scale = 1.15 - 0.13 * ease
            x_frac = 0.35 + 0.30 * ease
            y_frac = 0.20 + 0.55 * ease

        crop_w = max(int(round(big_w / scale)), width)
        crop_h = max(int(round(big_h / scale)), height)
        crop_w = min(crop_w, big_w)
        crop_h = min(crop_h, big_h)

        avail_x = max(big_w - crop_w, 0)
        avail_y = max(big_h - crop_h, 0)
        x0 = int(np.clip(x_frac * max_dx, 0, avail_x))
        y0 = int(np.clip(y_frac * max_dy, 0, avail_y))

        patch = src[y0 : y0 + crop_h, x0 : x0 + crop_w]
        if patch.shape[1] != width or patch.shape[0] != height:
            resized = Image.fromarray(patch).resize(
                (width, height), Image.Resampling.BILINEAR
            )
            return np.array(resized)
        return patch

    return VideoClip(make_frame, duration=duration)


def _make_progress_bar_clip(duration: float, width: int, height: int) -> VideoClip:
    """Render an animated retro cream/ink bottom progress bar across the video."""
    bar_h = 10

    def make_frame(t: float) -> np.ndarray:
        p = min(max(t / max(duration, 0.1), 0.0), 1.0)
        frame = np.zeros((height, width, 4), dtype=np.uint8)
        fill_w = int(width * p)
        frame[height - bar_h : height, :, :] = [30, 27, 24, 150]
        if fill_w > 0:
            frame[height - bar_h : height, :fill_w, :] = [242, 184, 75, 240]
        return frame

    return VideoClip(make_frame, duration=duration)


def assemble_video(
    media_paths: list[Path],
    audio_path: Path,
    word_timings: list[WordTiming],
    video_format: str,
    output_path: Path,
    scenes: list[Scene] | None = None,
) -> Path:
    """Assemble retro cartoon scenes, transitions, hooks, embedded subtitles, and audio."""
    spec = FORMAT_SPECS[video_format]
    output_path.parent.mkdir(parents=True, exist_ok=True)

    audio_clip = AudioFileClip(str(audio_path))
    total_duration = max(audio_clip.duration, 1.0)
    num_scenes = max(len(media_paths), 1)
    per_scene_duration = total_duration / num_scenes
    transition_dur = min(0.30, per_scene_duration * 0.2) if num_scenes > 1 else 0.0

    visual_clips = []
    opened_video_clips = []
    hook_clips = []

    try:
        for idx, path in enumerate(media_paths):
            clip_dur = per_scene_duration + (transition_dur if idx > 0 else 0.0)
            if path.suffix.lower() in (".mp4", ".mov", ".webm"):
                vclip = VideoFileClip(str(path))
                opened_video_clips.append(vclip)
                vclip = vclip.resized((spec.width, spec.height))
                scene_clip = _fit_clip_to_duration(vclip, clip_dur)
            else:
                scene_clip = _make_animated_cartoon_clip(
                    path, clip_dur, spec.width, spec.height, scene_index=idx
                )

            if idx > 0 and transition_dur > 0:
                scene_clip = scene_clip.with_effects([vfx.CrossFadeIn(transition_dur)])
            visual_clips.append(scene_clip)

            if scenes and idx < len(scenes) and scenes[idx].on_screen_hook.strip():
                hook_start = idx * per_scene_duration
                hook_dur = min(2.4, per_scene_duration * 0.85)
                hook_clips.append(
                    _make_spring_hook_clip(
                        text=scenes[idx].on_screen_hook,
                        start=hook_start,
                        duration=hook_dur,
                        width=spec.width,
                        height=spec.height,
                        is_shorts=(video_format == "shorts"),
                    )
                )

        if len(visual_clips) > 1 and transition_dur > 0:
            base_video = concatenate_videoclips(
                visual_clips, padding=-transition_dur, method="compose"
            ).with_duration(total_duration)
        else:
            base_video = concatenate_videoclips(
                visual_clips, method="compose"
            ).with_duration(total_duration)

        caption_clips = []
        font_size = 62 if video_format == "shorts" else 50
        for text, start, end in _group_words_into_captions(word_timings):
            if start >= total_duration:
                continue
            clipped_end = min(end, total_duration)
            frame = _render_caption_frame(text, spec.width, spec.height, font_size)
            c_clip = (
                ImageClip(frame)
                .with_start(start)
                .with_duration(max(clipped_end - start, 0.15))
            )
            caption_clips.append(c_clip)

        progress_clip = _make_progress_bar_clip(total_duration, spec.width, spec.height)

        final_video = CompositeVideoClip(
            [base_video, *hook_clips, *caption_clips, progress_clip],
            size=(spec.width, spec.height),
        ).with_audio(audio_clip)

        final_video.write_videofile(
            str(output_path),
            fps=30,
            codec="libx264",
            audio_codec="aac",
            preset="medium",
            threads=4,
            logger=None,
        )
        final_video.close()
    finally:
        audio_clip.close()
        for vclip in opened_video_clips:
            vclip.close()

    return output_path
