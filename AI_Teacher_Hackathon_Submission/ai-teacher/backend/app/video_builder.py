"""
video_builder.py — Assembles the final AI Teaching Video (section 9).

Pipeline per lesson segment:
  1. speech audio generated via tts.py (in the requested language)
  2. a subject-aware slide rendered via visuals.py (diagram/graph/equation/etc.)
  3. an animated avatar (avatar.py) composited into the corner, lip-synced
     (approximately) to the audio duration
  4. segment clip = slide (static) + avatar (animated) + narration audio

All segment clips are concatenated into one MP4 lesson video.
"""
import os
import uuid
import numpy as np
from moviepy import (
    ImageClip, AudioFileClip, CompositeVideoClip, concatenate_videoclips,
    concatenate_audioclips,
)

from . import tts, visuals, avatar

STATIC_DIR = os.path.join(os.path.dirname(__file__), "static")
VIDEO_DIR = os.path.join(STATIC_DIR, "videos")
AUDIO_DIR = os.path.join(STATIC_DIR, "audio")
SLIDE_DIR = os.path.join(STATIC_DIR, "slides")

for d in (VIDEO_DIR, AUDIO_DIR, SLIDE_DIR):
    os.makedirs(d, exist_ok=True)


def _avatar_clip(duration: float, position=("right", "bottom")):
    frames = avatar.build_avatar_frame_sequence(duration)
    clips = []
    for img, dur in frames:
        arr = np.array(img)  # RGBA
        clip = ImageClip(arr, duration=dur, is_mask=False)
        clips.append(clip)
    seq = concatenate_videoclips(clips, method="chain")
    seq = seq.with_position(position)
    safe_end = min(duration, seq.duration)
    return seq.subclipped(0, safe_end)


def build_segment_clip(segment: dict, subject: str, index: int, total: int,
                        language: str, session_id: str):
    # 1. narration audio (explanation + example, spoken together)
    narration_text = segment.get("explanation", "")
    if segment.get("example"):
        narration_text += ". For example: " + segment["example"]
    audio_path = os.path.join(AUDIO_DIR, f"{session_id}_seg{index}.mp3")
    audio_path = tts.generate_speech(narration_text, language, audio_path)
    audio_clip = AudioFileClip(audio_path)
    duration = max(2.0, audio_clip.duration)

    # 2. slide image
    slide_path = os.path.join(SLIDE_DIR, f"{session_id}_seg{index}.png")
    visuals.render_slide(segment, subject, index, total, slide_path)
    slide_clip = ImageClip(slide_path, duration=duration)

    # 3. animated avatar overlay, bottom-right corner
    av_clip = _avatar_clip(duration).with_position((950, 470))

    composite = CompositeVideoClip([slide_clip, av_clip], size=(1280, 720))
    composite = composite.with_duration(duration).with_audio(audio_clip)
    return composite


def build_lesson_video(lesson_plan: dict, language: str, session_id: str = None) -> dict:
    session_id = session_id or str(uuid.uuid4())[:10]
    subject = lesson_plan.get("meta", {}).get("subject", "general")
    segments = lesson_plan.get("segments", [])
    total = len(segments)

    clips = []

    # Intro "slide" using the first segment's visual style but the lesson intro text
    intro_segment = {
        "title": lesson_plan.get("title", "Lesson"),
        "explanation": lesson_plan.get("introduction", ""),
        "example": "",
        "visual_type": "diagram",
        "visual_description": lesson_plan.get("title", ""),
    }
    clips.append(build_segment_clip(intro_segment, subject, 0, total, language, session_id))

    for i, seg in enumerate(segments, start=1):
        clips.append(build_segment_clip(seg, subject, i, total, language, session_id))

    closing_segment = {
        "title": "Summary",
        "explanation": lesson_plan.get("closing_summary", ""),
        "example": "",
        "visual_type": "process",
        "visual_description": "summary",
    }
    clips.append(build_segment_clip(closing_segment, subject, total + 1, total, language, session_id))

    final = concatenate_videoclips(clips, method="compose")
    out_path = os.path.join(VIDEO_DIR, f"lesson_{session_id}.mp4")
    final.write_videofile(out_path, fps=15, codec="libx264", audio_codec="aac",
                           threads=2, logger=None)

    for c in clips:
        c.close()
    final.close()

    return {
        "session_id": session_id,
        "video_path": out_path,
        "video_url": f"/static/videos/{os.path.basename(out_path)}",
        "duration_seconds": final.duration if hasattr(final, "duration") else None,
    }
