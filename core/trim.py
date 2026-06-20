"""Pure helpers for the audio trim feature — no tkinter, no I/O."""
from __future__ import annotations

import numpy as np


def slice_audio(samples: np.ndarray, sr: int, start: float, end: float) -> np.ndarray:
    """Return the [start, end] second window of a mono sample array.

    Indices are clamped to the array bounds. If ``end <= start`` the result is empty.
    """
    a = max(0, int(round(start * sr)))
    b = min(len(samples), int(round(end * sr)))
    if b <= a:
        return samples[0:0]
    return samples[a:b]


def clamp_range(start: float, end: float, duration: float, min_len: float = 0.5) -> tuple[float, float]:
    """Clamp a selection to [0, duration], uncrossing handles and enforcing min length."""
    duration = max(0.0, float(duration))
    min_len = min(min_len, duration)
    start = min(max(0.0, float(start)), duration)
    end = min(max(0.0, float(end)), duration)
    if end < start:
        start, end = end, start
    if end - start < min_len:
        end = min(duration, start + min_len)
        start = max(0.0, end - min_len)
    return start, end


def format_timecode(seconds: float) -> str:
    """Format seconds as ``m:ss.s`` (e.g. 63.4 -> '1:03.4')."""
    seconds = max(0.0, float(seconds))
    minutes = int(seconds // 60)
    rem = seconds - minutes * 60
    return f"{minutes}:{rem:04.1f}"


def parse_timecode(text: str) -> float | None:
    """Parse ``m:ss.s`` or plain seconds into a float. Return None if unparseable."""
    text = text.strip()
    if not text:
        return None
    try:
        if ":" in text:
            mins, secs = text.split(":", 1)
            return int(mins) * 60 + float(secs)
        return float(text)
    except ValueError:
        return None


def should_trim(trim_start, trim_end) -> bool:
    """True when both bounds are set and describe a non-empty window."""
    return trim_start is not None and trim_end is not None and trim_end > trim_start


def apply_trim(audio, trim_start, trim_end):
    """Return ``audio`` subclipped to the window, or unchanged if no valid trim.

    ``audio`` is any object exposing moviepy v2's ``subclipped(start, end)``.
    """
    if should_trim(trim_start, trim_end):
        return audio.subclipped(trim_start, trim_end)
    return audio
