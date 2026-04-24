import os
from functools import lru_cache
from typing import List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

from core.transcriber import Segment, Word

_FONT_CANDIDATES = [
    "/usr/share/fonts/truetype/liberation/LiberationSans-Bold.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    "/usr/share/fonts/truetype/freefont/FreeSansBold.ttf",
    "/usr/share/fonts/truetype/ubuntu/Ubuntu-B.ttf",
    "/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf",
    "/System/Library/Fonts/Helvetica.ttc",
    "C:/Windows/Fonts/arialbd.ttf",
]

_font_cache: dict = {}


def _load_font(size: int, font_path: str = "") -> ImageFont.ImageFont:
    key = (size, font_path)
    if key in _font_cache:
        return _font_cache[key]
    font = None
    if font_path and os.path.exists(font_path):
        try:
            font = ImageFont.truetype(font_path, size)
        except Exception:
            font = None
    if font is None:
        for path in _FONT_CANDIDATES:
            if os.path.exists(path):
                try:
                    font = ImageFont.truetype(path, size)
                    break
                except Exception:
                    continue
    if font is None:
        try:
            font = ImageFont.load_default(size=size)
        except TypeError:
            font = ImageFont.load_default()
    _font_cache[key] = font
    return font


def _text_width(font: ImageFont.ImageFont, text: str) -> int:
    try:
        return int(font.getlength(text))
    except AttributeError:
        return font.getsize(text)[0]  # type: ignore[attr-defined]


def _dim(color: Tuple[int, int, int], factor: float) -> Tuple[int, int, int]:
    return tuple(max(0, int(c * factor)) for c in color)  # type: ignore[return-value]


def _active_segment(segments: List[Segment], t: float) -> Optional[Segment]:
    """Return the segment active at time t, or the most recently ended one."""
    for seg in segments:
        if seg.start <= t < seg.end:
            return seg
    # Show segment for up to 0.4s after it ends
    for seg in reversed(segments):
        if seg.start <= t and t < seg.end + 0.4:
            return seg
        if seg.start <= t:
            break
    return None


def _current_word_idx(words: List[Word], t: float) -> int:
    idx = -1
    for i, w in enumerate(words):
        if w.start <= t:
            idx = i
    return idx


def render_frame(
    gif_frame: Image.Image,
    segments: List[Segment],
    t: float,
    font_size: int = 40,
    text_color: Tuple[int, int, int] = (255, 255, 255),
    highlight_color: Tuple[int, int, int] = (255, 220, 0),
    watermark: Optional[Image.Image] = None,
    font_path: str = "",
) -> Image.Image:
    frame = gif_frame.convert("RGB")

    def _apply_watermark(img_rgba: Image.Image) -> Image.Image:
        if watermark is not None:
            return Image.alpha_composite(img_rgba, watermark)
        return img_rgba

    if not segments:
        if watermark is not None:
            return _apply_watermark(frame.convert("RGBA")).convert("RGB")
        return frame

    seg = _active_segment(segments, t)
    if seg is None or not seg.words:
        return frame

    width, height = frame.size
    font = _load_font(font_size, font_path)
    space_w = _text_width(font, " ")
    line_h = int(font_size * 1.45)
    h_pad = max(24, int(width * 0.05))
    max_line_w = width - 2 * h_pad

    # ---- Word wrap --------------------------------------------------------
    # Each line: list of (word_index_in_seg, word_text, x_offset_within_line)
    lines: List[List[Tuple[int, str, int]]] = []
    cur_line: List[Tuple[int, str, int]] = []
    cur_x = 0

    for i, word in enumerate(seg.words):
        if not word.text:
            continue
        w = _text_width(font, word.text)
        if cur_x + w > max_line_w and cur_line:
            lines.append(cur_line)
            cur_line = [(i, word.text, 0)]
            cur_x = w + space_w
        else:
            cur_line.append((i, word.text, cur_x))
            cur_x += w + space_w

    if cur_line:
        lines.append(cur_line)

    if not lines:
        return frame

    # ---- Limit visible lines to a window around the current word ----------
    MAX_LINES = 3
    cur_wi = _current_word_idx(seg.words, t)

    current_line_idx = 0
    for li, line in enumerate(lines):
        if any(wi == cur_wi for wi, _, _ in line):
            current_line_idx = li
            break

    if len(lines) > MAX_LINES:
        start = max(0, current_line_idx - 1)
        end = min(len(lines), start + MAX_LINES)
        start = max(0, end - MAX_LINES)
        lines = lines[start:end]

    # ---- Draw -------------------------------------------------------------
    v_pad = 14
    text_area_h = len(lines) * line_h + 2 * v_pad
    bar_top = height - text_area_h

    overlay = Image.new("RGBA", (width, height), (0, 0, 0, 0))
    ov_draw = ImageDraw.Draw(overlay)
    ov_draw.rectangle([(0, bar_top), (width, height)], fill=(0, 0, 0, 185))

    frame_rgba = Image.alpha_composite(frame.convert("RGBA"), overlay)
    draw = ImageDraw.Draw(frame_rgba)

    for li, line in enumerate(lines):
        if not line:
            continue
        last_wi, last_wt, last_xo = line[-1]
        line_width = last_xo + _text_width(font, last_wt)
        x_start = (width - line_width) // 2
        y = bar_top + v_pad + li * line_h

        for wi, wt, xo in line:
            x = x_start + xo
            if wi < cur_wi:
                color = _dim(text_color, 0.55)
            elif wi == cur_wi:
                color = highlight_color
            else:
                color = text_color
            draw.text((x, y), wt, font=font, fill=color)

    return _apply_watermark(frame_rgba).convert("RGB")
