"""
tts.py — Text-to-speech.

Default engine: gTTS (free, no API key, decent quality, wide language
support) — good enough for a working prototype.

Swap point: for a more "human-like" premium voice, drop in ElevenLabs /
Azure Neural TTS / OpenAI TTS here behind the same generate_speech()
interface — the rest of the app (video assembly, timing) doesn't change.
"""
import os
import wave
import struct
import math
from gtts import gTTS
from .translator import resolve_language


def _estimate_duration_seconds(text: str) -> float:
    words = max(1, len(text.split()))
    return max(1.5, words / 2.6)  # ~155 words/minute average speech rate


def _write_silent_placeholder_wav(path: str, duration: float, tone_hz: float = 220.0):
    """Fallback audio generator used only when the TTS provider is
    unreachable (e.g. no internet access). Produces a short, quiet tone
    envelope (not silence) so it's obvious in a demo that audio *would*
    play, while keeping the video pipeline fully functional offline."""
    framerate = 16000
    n_frames = int(duration * framerate)
    with wave.open(path, "w") as w:
        w.setnchannels(1)
        w.setsampwidth(2)
        w.setframerate(framerate)
        for i in range(n_frames):
            t = i / framerate
            # quiet fading tone as a placeholder, not real speech
            amp = 1200 * math.exp(-0.5 * (t % 1.2))
            sample = int(amp * math.sin(2 * math.pi * tone_hz * t))
            w.writeframes(struct.pack("<h", sample))


def generate_speech(text: str, language_name: str, out_path: str) -> str:
    """Generates narration audio for `text`. Tries real TTS (gTTS) first;
    if the network/provider is unavailable, falls back to a placeholder
    audio track of the correct estimated duration so the rest of the
    video pipeline (timing, avatar sync, slide duration) still works.
    Returns the actual path written (extension may change on fallback)."""
    _, gtts_code = resolve_language(language_name)
    text = text.strip() or "..."
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    try:
        tts = gTTS(text=text, lang=gtts_code)
        tts.save(out_path)
        return out_path
    except Exception as e:
        fallback_path = os.path.splitext(out_path)[0] + ".wav"
        duration = _estimate_duration_seconds(text)
        _write_silent_placeholder_wav(fallback_path, duration)
        print(f"[tts] WARNING: real TTS unavailable ({e}); wrote placeholder audio "
              f"({duration:.1f}s) instead. This works fully once the server has "
              f"normal internet access.")
        return fallback_path
