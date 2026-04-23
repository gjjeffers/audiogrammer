from pathlib import Path
from typing import Callable, List, Optional, Tuple

import numpy as np
from PIL import Image

from core.renderer import render_frame
from core.transcriber import Segment


# ---------------------------------------------------------------------------
# GIF helpers
# ---------------------------------------------------------------------------

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
    if total <= 0:
        return frames[0]
    t_mod = t % total
    elapsed = 0.0
    for frame, dur in zip(frames, durations):
        elapsed += dur
        if t_mod < elapsed:
            return frame
    return frames[-1]


# ---------------------------------------------------------------------------
# Scaling
# ---------------------------------------------------------------------------

def _make_scaler(
    src_w: int,
    src_h: int,
    target_size: Optional[Tuple[int, int]],
    min_width: int = 480,
) -> Tuple[Callable[[Image.Image], Image.Image], Tuple[int, int]]:
    """Return (scale_fn, output_size)."""
    if target_size is not None:
        tw, th = target_size
        scale = min(tw / src_w, th / src_h)
        new_w, new_h = int(src_w * scale), int(src_h * scale)
        ox, oy = (tw - new_w) // 2, (th - new_h) // 2

        def _scale(frame: Image.Image) -> Image.Image:
            scaled = frame.resize((new_w, new_h), Image.LANCZOS)
            canvas = Image.new("RGBA", (tw, th), (0, 0, 0, 255))
            canvas.paste(scaled, (ox, oy))
            return canvas

        return _scale, (tw, th)

    if src_w < min_width:
        factor = min_width / src_w
        new_size = (int(src_w * factor), int(src_h * factor))

        def _scale(frame: Image.Image) -> Image.Image:  # type: ignore[misc]
            return frame.resize(new_size, Image.LANCZOS)

        return _scale, new_size

    return lambda f: f, (src_w, src_h)


# ---------------------------------------------------------------------------
# Background loader — returns (get_frame_fn, cleanup_fn)
# ---------------------------------------------------------------------------

def _load_background(
    bg_path: str,
    target_size: Optional[Tuple[int, int]],
    status_callback: Optional[Callable[[str], None]],
) -> Tuple[Callable[[float], Image.Image], Callable[[], None]]:
    ext = Path(bg_path).suffix.lower()

    if ext == ".gif":
        if status_callback:
            status_callback("Loading GIF frames...")
        frames, durations = _load_gif(bg_path)
        scaler, _ = _make_scaler(frames[0].size[0], frames[0].size[1], target_size)
        frames = [scaler(f) for f in frames]
        total = sum(durations)

        def get_gif_frame(t: float) -> Image.Image:
            return _frame_at(frames, durations, total, t)

        return get_gif_frame, lambda: None

    elif ext in {".jpg", ".jpeg", ".png", ".bmp", ".tiff", ".tif", ".webp"}:
        if status_callback:
            status_callback("Loading image background...")
        img = Image.open(bg_path).convert("RGBA")
        scaler, _ = _make_scaler(img.size[0], img.size[1], target_size)
        frame = scaler(img)

        return lambda t: frame, lambda: None

    else:
        # MP4 / any video — decode on demand to keep memory low
        try:
            from moviepy import VideoFileClip
        except ImportError:
            from moviepy.editor import VideoFileClip  # type: ignore[no-redef]

        if status_callback:
            status_callback("Loading video background...")

        bg_clip = VideoFileClip(bg_path)
        bg_duration = bg_clip.duration
        src_w = int(bg_clip.size[0])
        src_h = int(bg_clip.size[1])
        scaler, _ = _make_scaler(src_w, src_h, target_size)

        def get_mp4_frame(t: float) -> Image.Image:
            t_mod = t % bg_duration
            arr = bg_clip.get_frame(t_mod)
            frame = Image.fromarray(arr.astype("uint8")).convert("RGBA")
            return scaler(frame)

        return get_mp4_frame, bg_clip.close


# ---------------------------------------------------------------------------
# Main entry point
# ---------------------------------------------------------------------------

def compose_video(
    bg_path: str,
    audio_path: str,
    segments: List[Segment],
    output_path: str,
    fps: int = 24,
    font_size: int = 40,
    text_color: Tuple[int, int, int] = (255, 255, 255),
    highlight_color: Tuple[int, int, int] = (255, 220, 0),
    target_size: Optional[Tuple[int, int]] = None,
    crf: int = 18,
    preset: str = "slow",
    status_callback: Optional[Callable[[str], None]] = None,
    progress_callback: Optional[Callable[[float], None]] = None,
) -> None:
    try:
        from moviepy import AudioFileClip, VideoClip
    except ImportError:
        from moviepy.editor import AudioFileClip, VideoClip  # type: ignore[no-redef]

    get_bg_frame, bg_cleanup = _load_background(bg_path, target_size, status_callback)

    if status_callback:
        status_callback("Loading audio...")

    audio = AudioFileClip(audio_path)
    duration = audio.duration
    total_frames = max(1, int(duration * fps))
    rendered_count = [0]

    def make_frame(t: float) -> np.ndarray:
        bg = get_bg_frame(t)
        img = render_frame(bg, segments, t, font_size, text_color, highlight_color)
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
        ffmpeg_params=["-crf", str(crf), "-preset", preset],
        logger=None,
    )

    audio.close()
    bg_cleanup()
