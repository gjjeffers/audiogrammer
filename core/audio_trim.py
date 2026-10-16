"""Cut an audio window out of a file with ffmpeg, ready for Whisper."""
from __future__ import annotations

import subprocess

import numpy as np

WHISPER_SAMPLE_RATE = 16000


def _ffmpeg_exe() -> str:
    """Prefer the ffmpeg bundled with imageio-ffmpeg; fall back to PATH."""
    try:
        import imageio_ffmpeg
        return imageio_ffmpeg.get_ffmpeg_exe()
    except Exception:
        return "ffmpeg"


def trim_audio_ffmpeg(
    audio_path: str,
    start: float,
    end: float,
    sr: int = WHISPER_SAMPLE_RATE,
) -> np.ndarray:
    """Decode only the [start, end] second window of ``audio_path`` with ffmpeg.

    Returns mono float32 samples at ``sr`` in [-1, 1] — the same format as
    ``whisper.load_audio`` — so the result can be passed straight to Whisper.
    ffmpeg seeks to ``start`` before decoding, so the part of the file outside
    the window is never decoded or held in memory.
    """
    cmd = [
        _ffmpeg_exe(), "-nostdin", "-v", "error",
        "-ss", f"{start:.3f}", "-t", f"{end - start:.3f}",
        "-i", audio_path,
        "-vn", "-ac", "1", "-ar", str(sr),
        "-f", "s16le", "-",
    ]
    proc = subprocess.run(cmd, capture_output=True)
    if proc.returncode != 0:
        detail = proc.stderr.decode(errors="replace").strip()
        raise RuntimeError(f"ffmpeg failed to trim audio: {detail}")
    return np.frombuffer(proc.stdout, np.int16).astype(np.float32) / 32768.0
