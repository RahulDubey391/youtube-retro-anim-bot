from __future__ import annotations

from pydantic import BaseModel, Field


class Scene(BaseModel):
    scene_number: int = Field(..., description="1-based scene index")
    narration: str = Field(..., description="Spoken voiceover line(s) for this scene")
    visual_prompt: str = Field(
        ...,
        description="Detailed cinematic prompt for Veo/Imagen (no on-screen text)",
    )
    on_screen_hook: str = Field(
        default="",
        description="Optional short 2-4 word emphasis callout for the scene",
    )


class VideoPlan(BaseModel):
    topic: str = Field(..., description="Core topic of the video")
    niche: str = Field(..., description="Target niche")
    video_format: str = Field(..., description="'shorts' or 'long'")
    title: str = Field(
        ...,
        description="High-CTR viral YouTube title (max 95 chars, curiosity gap)",
    )
    description: str = Field(
        ...,
        description="SEO-optimized YouTube description with hook, summary, and hashtags",
    )
    hashtags: list[str] = Field(
        ...,
        description="5-10 relevant viral hashtags including #Shorts when applicable",
    )
    tags: list[str] = Field(
        ...,
        description="10-15 YouTube SEO keyword tags (without #)",
    )
    thumbnail_prompt: str = Field(
        ...,
        description="Detailed visual prompt for a bold, high-contrast thumbnail background",
    )
    thumbnail_text: str = Field(
        ...,
        description="2-4 punchy uppercase words to overlay on the thumbnail",
    )
    scenes: list[Scene] = Field(..., description="Ordered list of scenes")


class WordTiming(BaseModel):
    text: str
    start: float
    end: float


class UploadResult(BaseModel):
    drive_folder_id: str | None = None
    drive_video_id: str | None = None
    drive_video_url: str | None = None
    drive_thumbnail_url: str | None = None
    youtube_video_id: str | None = None
    youtube_url: str | None = None

