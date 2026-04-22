from typing import Callable, List, Optional, Tuple

import numpy as np
from PIL import Image

from core.renderer import render_frame
from core.transcriber import Segment


def _load_gif(gif_path: str) -> Tuple[List[Image.Image], List[float]]:
    """Return (frames, durations_in_seconds). Durations default to 100ms."""
    gif = Image.open(gif_path)
    frames: List[Image.Image] = []
    durations: List[float] = []
    try:
        while True:
            ms = gif.info.get("duration", 100)
            frames.append(gif.copy().convert("RGBA"))
            durations.append(max(ms, 20) / 1000.0)
            gif.seek(gif.tell() + 1)
    except EOFError:
        pass
    return frames, durations


def _frame_at(frames: List[Image.Image], durations: List[float], total: float, t: float) -> Image.Image:
    """Return the GIF frame for time t (looping)."""
    if total <= 0:
        return frames[0]
    t_mod = t % total
    elapsed = 0.0
    for frame, dur in zip(frames, durations):
        elapsed += dur
        if t_mod < elapsed:
            return frame
    return frames[-1]


def _ensure_min_size(frames: List[Image.Image], min_width: int = 480) -> List[Image.Image]:
    """Upscale frames if the GIF is too small for readable text."""
    w, h = frames[0].size
    if w < min_width:
        scale = min_width / w
        new_size = (int(w * scale), int(h * scale))
        frames = [f.resize(new_size, Image.LANCZOS) for f in frames]
    return frames


def compose_video(
    gif_path: str,
    audio_path: str,
    segments: List[Segment],
    output_path: str,
    fps: int = 24,
    font_size: int = 40,
    text_color: Tuple[int, int, int] = (255, 255, 255),
    highlight_color: Tuple[int, int, int] = (255, 220, 0),
    status_callback: Optional[Callable[[str], None]] = None,
    progress_callback: Optional[Callable[[float], None]] = None,
) -> None:
    try:
        from moviepy import AudioFileClip, VideoClip
    except ImportError:
        from moviepy.editor import AudioFileClip, VideoClip  # type: ignore[no-redef]

    if status_callback:
        status_callback("Loading GIF frames...")

    frames, durations = _load_gif(gif_path)
    frames = _ensure_min_size(frames)
    total_gif_dur = sum(durations)
    width, height = frames[0].size

    if status_callback:
        status_callback("Loading audio...")

    audio = AudioFileClip(audio_path)
    duration = audio.duration
    total_frames = max(1, int(duration * fps))
    rendered_count = [0]

    def make_frame(t: float) -> np.ndarray:
        gif_frame = _frame_at(frames, durations, total_gif_dur, t)
        img = render_frame(gif_frame, segments, t, font_size, text_color, highlight_color)
        rendered_count[0] += 1
        if progress_callback:
            progress_callback(min(rendered_count[0] / total_frames, 1.0))
        return np.array(img.convert("RGB"))

    if status_callback:
        status_callback("Rendering video frames...")

    clip = VideoClip(make_frame, duration=duration)
    clip = clip.with_fps(fps)
    clip = clip.with_audio(audio)

    if status_callback:
        status_callback("Encoding video (this may take a while)...")

    clip.write_videofile(
        output_path,
        fps=fps,
        codec="libx264",
        audio_codec="aac",
        logger=None,
    )

    audio.close()
