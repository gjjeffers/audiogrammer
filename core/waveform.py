import math
from dataclasses import dataclass, field
from typing import Optional, Tuple

import numpy as np
from PIL import Image, ImageDraw


@dataclass
class WaveformConfig:
    enabled: bool = False
    mode: str = "reactive"            # "reactive" (FFT spectrum) | "progress" (static waveform + playhead)
    style: str = "bars"              # "line" | "bars" | "circular"
    color: Tuple[int, int, int] = field(default_factory=lambda: (255, 255, 255))
    gradient_color: Optional[Tuple[int, int, int]] = None  # None = solid fill
    opacity: float = 0.9             # 0..1
    placement_mode: str = "stretch"  # "stretch" | "tile"
    region: str = "bottom"           # stretch: "top" | "middle" | "bottom"
    cell: str = "middle-center"      # tile: "{top|middle|bottom}-{left|center|right}"
    sensitivity: float = 1.0         # gain multiplier
    smoothing: float = 0.5           # 0..1 temporal EMA (reactive only)
    mirror: bool = False             # symmetric reflection about region center
    bar_count: int = 48              # bars / circular spokes
    thickness: int = 3               # line width (line style)
    height_frac: float = 0.85        # fraction of region used by the viz


_ANALYSIS_SR = 22050


# ---------------------------------------------------------------------------
# Audio analysis (precomputed once per render)
# ---------------------------------------------------------------------------

def _to_mono(audio, sr: int) -> np.ndarray:
    samples = audio.to_soundarray(fps=sr)
    if samples.ndim == 2:
        samples = samples.mean(axis=1)
    return samples.astype(np.float64)


def _normalize(arr: np.ndarray, sensitivity: float) -> np.ndarray:
    peak = float(np.max(arr)) if arr.size else 0.0
    if peak <= 1e-9:
        return np.zeros_like(arr)
    out = (arr / peak) * sensitivity
    return np.clip(out, 0.0, 1.0)


def analyze_audio(audio, fps: int, total_frames: int, config: WaveformConfig,
                  cancel_event=None) -> np.ndarray:
    """Precompute per-render visualization data.

    reactive -> shape (total_frames, bar_count) levels in 0..1
    progress -> shape (bar_count,) static envelope in 0..1

    ``cancel_event`` (a threading.Event) is polled during the reactive
    per-frame loop so a long analysis can be interrupted promptly.
    """
    mono = _to_mono(audio, _ANALYSIS_SR)
    n = mono.size
    bars = max(2, int(config.bar_count))

    if config.mode == "progress":
        # Peak envelope across bar_count buckets over the whole track.
        env = np.zeros(bars, dtype=np.float64)
        edges = np.linspace(0, n, bars + 1, dtype=int)
        absmono = np.abs(mono)
        for i in range(bars):
            a, b = edges[i], edges[i + 1]
            if b > a:
                env[i] = absmono[a:b].max()
        return _normalize(env, config.sensitivity)

    # ---- reactive: FFT spectrum per frame --------------------------------
    win = 2048
    half = win // 2
    # Log-spaced frequency band edges over the usable spectrum.
    band_edges = np.logspace(
        math.log10(1), math.log10(half), bars + 1
    ).astype(int)
    band_edges = np.clip(band_edges, 1, half)

    window_fn = np.hanning(win)
    levels = np.zeros((total_frames, bars), dtype=np.float64)

    for f in range(total_frames):
        if cancel_event is not None and (f & 63) == 0 and cancel_event.is_set():
            raise InterruptedError
        center = int((f / fps) * _ANALYSIS_SR)
        start = center - half
        seg = np.zeros(win, dtype=np.float64)
        a = max(0, start)
        b = min(n, start + win)
        if b > a:
            seg[a - start:b - start] = mono[a:b]
        spectrum = np.abs(np.fft.rfft(seg * window_fn))
        for i in range(bars):
            lo, hi = band_edges[i], max(band_edges[i] + 1, band_edges[i + 1])
            levels[f, i] = spectrum[lo:hi].mean() if hi > lo else 0.0

    # Temporal EMA smoothing across frames.
    s = float(np.clip(config.smoothing, 0.0, 0.99))
    if s > 0 and total_frames > 1:
        for f in range(1, total_frames):
            levels[f] = s * levels[f - 1] + (1.0 - s) * levels[f]

    return _normalize(levels, config.sensitivity)


# ---------------------------------------------------------------------------
# Placement
# ---------------------------------------------------------------------------

def compute_region(frame_size: Tuple[int, int], config: WaveformConfig) -> Tuple[int, int, int, int]:
    w, h = frame_size
    if config.placement_mode == "tile":
        rows = {"top": 0, "middle": 1, "bottom": 2}
        cols = {"left": 0, "center": 1, "right": 2}
        parts = config.cell.split("-")
        r = rows.get(parts[0], 1)
        c = cols.get(parts[1] if len(parts) > 1 else "center", 1)
        cw, ch = w // 3, h // 3
        pad_x, pad_y = int(cw * 0.08), int(ch * 0.08)
        x0 = c * cw + pad_x
        y0 = r * ch + pad_y
        return (x0, y0, x0 + cw - 2 * pad_x, y0 + ch - 2 * pad_y)

    # stretch: full width, one vertical third
    thirds = {"top": 0, "middle": 1, "bottom": 2}
    t = thirds.get(config.region, 2)
    th = h // 3
    return (0, t * th, w, t * th + th)


# ---------------------------------------------------------------------------
# Drawing
# ---------------------------------------------------------------------------

def _lerp_color(c0: Tuple[int, int, int], c1: Tuple[int, int, int], f: float) -> Tuple[int, int, int]:
    f = max(0.0, min(1.0, f))
    return tuple(int(c0[i] + (c1[i] - c0[i]) * f) for i in range(3))  # type: ignore[return-value]


def _dim(color: Tuple[int, int, int], factor: float) -> Tuple[int, int, int]:
    return tuple(max(0, int(c * factor)) for c in color)  # type: ignore[return-value]


def draw_waveform(
    bg_rgba: Image.Image,
    config: WaveformConfig,
    region_box: Tuple[int, int, int, int],
    data: np.ndarray,
    frame_idx: int,
    total_frames: int,
) -> Image.Image:
    """Composite the waveform onto bg_rgba (RGBA) and return it."""
    x0, y0, x1, y1 = region_box
    rw, rh = max(1, x1 - x0), max(1, y1 - y0)
    layer = Image.new("RGBA", bg_rgba.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(layer)

    if config.mode == "progress":
        levels = np.asarray(data, dtype=np.float64)
        playhead = (frame_idx + 1) / max(1, total_frames)
    else:
        idx = min(max(0, frame_idx), data.shape[0] - 1)
        levels = np.asarray(data[idx], dtype=np.float64)
        playhead = None

    n = levels.size
    if n == 0:
        return bg_rgba

    color = config.color
    grad = config.gradient_color

    def bar_color(level: float, pos_frac: float) -> Tuple[int, int, int]:
        base = _lerp_color(color, grad, level) if grad is not None else color
        if playhead is not None and pos_frac > playhead:
            return _dim(base, 0.35)
        return base

    if config.style == "circular":
        cx, cy = x0 + rw / 2, y0 + rh / 2
        radius = min(rw, rh) / 2 * 0.45
        max_len = min(rw, rh) / 2 * config.height_frac - radius
        max_len = max(4.0, max_len)
        for i in range(n):
            ang = (i / n) * 2 * math.pi - math.pi / 2
            lv = float(levels[i])
            ln = radius + max_len * lv
            sx, sy = cx + radius * math.cos(ang), cy + radius * math.sin(ang)
            ex, ey = cx + ln * math.cos(ang), cy + ln * math.sin(ang)
            draw.line([(sx, sy), (ex, ey)], fill=bar_color(lv, i / n) + (255,),
                      width=max(1, config.thickness))
        if playhead is not None:
            # ring arc up to playhead
            draw.arc([cx - radius, cy - radius, cx + radius, cy + radius],
                     start=-90, end=-90 + 360 * playhead,
                     fill=color + (255,), width=max(1, config.thickness))

    elif config.style == "line":
        mid = y0 + rh / 2
        amp = (rh / 2) * config.height_frac if config.mirror else rh * config.height_frac
        width = max(1, config.thickness)
        pts = []
        for i in range(n):
            x = x0 + (i / max(1, n - 1)) * rw
            lv = float(levels[i])
            y = mid - amp * lv if config.mirror else y1 - amp * lv
            pts.append((x, y))
        # Draw per-segment so gradient and progress-playhead dimming apply.
        for i in range(len(pts) - 1):
            seg_fill = bar_color(float(levels[i]), i / n) + (255,)
            draw.line([pts[i], pts[i + 1]], fill=seg_fill, width=width, joint="curve")
            if config.mirror:
                a = (pts[i][0], mid + (mid - pts[i][1]))
                b = (pts[i + 1][0], mid + (mid - pts[i + 1][1]))
                draw.line([a, b], fill=seg_fill, width=width, joint="curve")

    else:  # bars
        slot = rw / n
        bw = max(1.0, slot * 0.7)
        gap = (slot - bw) / 2
        mid = y0 + rh / 2
        for i in range(n):
            lv = float(levels[i])
            bx0 = x0 + i * slot + gap
            bx1 = bx0 + bw
            if config.mirror:
                bh = (rh / 2) * config.height_frac * lv
                by0, by1 = mid - bh, mid + bh
            else:
                bh = rh * config.height_frac * lv
                by0, by1 = y1 - bh, y1
            if by1 - by0 < 1:
                continue
            r = min(bw / 2, (by1 - by0) / 2)
            draw.rounded_rectangle([bx0, by0, bx1, by1], radius=r,
                                   fill=bar_color(lv, i / n) + (255,))

    # Apply global opacity to the whole layer.
    if config.opacity < 1.0:
        alpha = layer.split()[3].point(lambda v: int(v * config.opacity))
        layer.putalpha(alpha)

    return Image.alpha_composite(bg_rgba, layer)
