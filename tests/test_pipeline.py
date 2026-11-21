from __future__ import annotations

import math
import struct
import wave
from pathlib import Path

from PIL import Image

from config import get_settings
from src.gemini_content import _overlay_thumbnail_text, record_topic_history, _load_history
from src.models import Scene, VideoPlan, WordTiming
from src.video_assembler import _group_words_into_captions, assemble_video
from src.youtube_uploader import _format_description


def _write_sine_wav(path: Path, duration_sec: float = 1.5, sample_rate: int = 22050) -> None:
    n_samples = int(duration_sec * sample_rate)
    with wave.open(str(path), "w") as wf:
        wf.setnchannels(1)
        wf.setsampwidth(2)
        wf.setframerate(sample_rate)
        frames = bytearray()
        for i in range(n_samples):
            val = int(8000 * math.sin(2 * math.pi * 440 * i / sample_rate))
            frames.extend(struct.pack("<h", val))
        wf.writeframes(bytes(frames))


def test_caption_grouping_and_description():
    timings = [
        WordTiming(text="Did", start=0.0, end=0.2),
        WordTiming(text="you", start=0.2, end=0.4),
        WordTiming(text="know", start=0.4, end=0.6),
        WordTiming(text="this", start=0.6, end=0.9),
    ]
    chunks = _group_words_into_captions(timings, words_per_chunk=3)
    assert len(chunks) == 2
    assert chunks[0][0] == "DID YOU KNOW"
    assert chunks[1][0] == "THIS"

    plan = VideoPlan(
        topic="Test Topic",
        niche="Psychology",
        video_format="shorts",
        title="Why Your Brain Lies To You",
        description="Hook line here.",
        hashtags=["#Shorts", "#Psychology"],
        tags=["psychology", "facts"],
        thumbnail_prompt="Dramatic brain illustration",
        thumbnail_text="BRAIN TRICK",
        scenes=[
            Scene(
                scene_number=1,
                narration="Your brain edits your memories.",
                visual_prompt="Glowing neural network",
            )
        ],
    )
    formatted = _format_description(plan)
    assert "#Shorts" in formatted
    assert "#Psychology" in formatted


def test_thumbnail_overlay_and_video_assembly(tmp_path: Path):
    img_path = tmp_path / "scene1.jpg"
    Image.new("RGB", (720, 1280), (40, 60, 120)).save(img_path)

    thumb = _overlay_thumbnail_text(
        Image.new("RGB", (1280, 720), (30, 30, 80)),
        "HIDDEN HISTORY",
    )
    assert thumb.size == (1280, 720)

    wav_path = tmp_path / "audio.wav"
    _write_sine_wav(wav_path, duration_sec=1.2)

    out_mp4 = tmp_path / "out.mp4"
    timings = [
        WordTiming(text="HIDDEN", start=0.0, end=0.5),
        WordTiming(text="HISTORY", start=0.5, end=1.0),
    ]
    result = assemble_video(
        media_paths=[img_path],
        audio_path=wav_path,
        word_timings=timings,
        video_format="shorts",
        output_path=out_mp4,
    )
    assert result.exists()
    assert result.stat().st_size > 1000


def test_history_deduplication(tmp_path: Path):
    hist = tmp_path / "history.json"
    record_topic_history("Topic A", hist)
    record_topic_history("Topic A", hist)
    record_topic_history("Topic B", hist)
    assert _load_history(hist) == ["Topic A", "Topic B"]


def test_settings_defaults():
    settings = get_settings()
    assert settings.default_format in ("shorts", "long")
    assert settings.youtube_privacy_status in ("private", "unlisted", "public")

