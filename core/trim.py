"""Pure helpers for the audio trim feature — no tkinter, no I/O."""
from __future__ import annotations

from typing import List, Optional, Tuple

import numpy as np

from core.transcriber import Segment, Word

# Silence kept before the first and after the last spoken word when auto-trimming.
SPEECH_PADDING = 0.25
# Auto-trim is skipped when it would cut less than this much (seconds).
_MIN_AUTO_TRIM = 0.05


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


def speech_window(
    segments: List[Segment],
    duration: float,
    padding: float = SPEECH_PADDING,
) -> Optional[Tuple[float, float]]:
    """Window (relative to the transcribed audio) from just before the first
    spoken word to just after the last one, or None if nothing worth trimming.

    ``duration`` is the length of the audio the segments were transcribed from.
    """
    words = [w for seg in segments for w in seg.words if w.text.strip()]
    if not words:
        return None
    start = max(0.0, min(w.start for w in words) - padding)
    end = min(duration, max(w.end for w in words) + padding)
    if end <= start or (start < _MIN_AUTO_TRIM and duration - end < _MIN_AUTO_TRIM):
        return None
    return start, end


def shift_segments(segments: List[Segment], delta: float) -> List[Segment]:
    """Return copies of ``segments`` with every time moved earlier by ``delta`` seconds."""
    def sh(t: float) -> float:
        return max(0.0, t - delta)

    return [
        Segment(
            text=seg.text,
            start=sh(seg.start),
            end=sh(seg.end),
            words=[Word(text=w.text, start=sh(w.start), end=sh(w.end)) for w in seg.words],
        )
        for seg in segments
    ]
