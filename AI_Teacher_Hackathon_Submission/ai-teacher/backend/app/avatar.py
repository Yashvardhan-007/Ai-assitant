"""
avatar.py — Human-like AI avatar presenter.

HONEST SCOPE NOTE: generating a photorealistic talking-head avatar (like
D-ID / HeyGen / Synthesia) requires a paid third-party API and network
access this environment doesn't have. This module ships a clean, working
stand-in: a friendly animated 2D character whose mouth opens/closes in
sync with the generated speech audio, so the "video-based AI teacher
presenter" requirement is genuinely functional end-to-end.

SWAP POINT: replace `frames_for_duration()` with a call to a real avatar
API (send the generated audio file, receive a talking-head video clip)
and splice that clip into the corner overlay in video_builder.py instead
of these PIL frames. The rest of the pipeline does not need to change.
"""
import os
from PIL import Image, ImageDraw

SIZE = 260
SKIN = (250, 214, 165, 255)
HAIR = (60, 40, 30, 255)
OUTLINE = (40, 30, 25, 255)


def _draw_face(mouth_open: float, blink: bool) -> Image.Image:
    """mouth_open: 0.0 (closed) .. 1.0 (wide open)"""
    img = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
    d = ImageDraw.Draw(img)
    cx, cy = SIZE // 2, SIZE // 2 + 10

    # head
    d.ellipse([cx - 90, cy - 100, cx + 90, cy + 100], fill=SKIN, outline=OUTLINE, width=3)
    # hair
    d.pieslice([cx - 92, cy - 110, cx + 92, cy + 40], 180, 360, fill=HAIR)
    # ears
    d.ellipse([cx - 100, cy - 15, cx - 80, cy + 20], fill=SKIN, outline=OUTLINE, width=2)
    d.ellipse([cx + 80, cy - 15, cx + 100, cy + 20], fill=SKIN, outline=OUTLINE, width=2)

    # eyes
    eye_h = 4 if blink else 14
    for ex in (cx - 32, cx + 32):
        d.ellipse([ex - 13, cy - 20 - eye_h // 2, ex + 13, cy - 20 + eye_h // 2],
                   fill=(255, 255, 255, 255), outline=OUTLINE, width=2)
        if not blink:
            d.ellipse([ex - 5, cy - 20 - 5, ex + 5, cy - 20 + 5], fill=(40, 30, 25, 255))

    # eyebrows
    d.line([cx - 45, cy - 42, cx - 18, cy - 38], fill=OUTLINE, width=4)
    d.line([cx + 18, cy - 38, cx + 45, cy - 42], fill=OUTLINE, width=4)

    # nose
    d.line([cx, cy - 5, cx - 6, cy + 15], fill=OUTLINE, width=3)

    # mouth (talking animation)
    mh = int(6 + mouth_open * 26)
    d.ellipse([cx - 26, cy + 35 - mh // 2, cx + 26, cy + 35 + mh // 2],
               fill=(150, 40, 40, 255), outline=OUTLINE, width=3)
    if mouth_open < 0.15:
        d.line([cx - 24, cy + 35, cx + 24, cy + 35], fill=OUTLINE, width=3)

    # collar / shoulders (simple "presenter" body)
    d.rectangle([cx - 70, cy + 95, cx + 70, SIZE], fill=(45, 85, 140, 255))

    return img


# Pre-render a small set of mouth-state frames once and reuse them —
# far cheaper than drawing per-video-frame.
_MOUTH_LEVELS = [0.0, 0.25, 0.5, 0.75, 1.0]
_FRAME_CACHE = {}


def get_frame(level_index: int, blink: bool = False):
    key = (level_index, blink)
    if key not in _FRAME_CACHE:
        _FRAME_CACHE[key] = _draw_face(_MOUTH_LEVELS[level_index], blink)
    return _FRAME_CACHE[key]


def build_avatar_frame_sequence(duration: float, fps: int = 8):
    """Returns a list of (image, frame_duration_seconds) approximating a
    talking mouth animation for the given duration, with an occasional blink."""
    import random
    import math
    frame_time = 1.0 / fps
    n = max(1, math.ceil(duration / frame_time) + 1)  # pad by 1 frame to avoid rounding underflow
    seq = []
    t = 0
    for i in range(n):
        blink = (i % 45 == 0)  # blink roughly every ~5-6s at fps=8
        level = random.choice([0, 1, 2, 3, 2, 1]) if not blink else 0
        seq.append((get_frame(level, blink), frame_time))
        t += frame_time
    return seq
