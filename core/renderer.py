import os
from typing import List, Optional, Tuple

from PIL import Image, ImageDraw, ImageFont

from core.color import dim
from core.fonts import load_weighted_font
from core.transcriber import Segment, Word
from core.transitions import TextTransition, composite_caption, transition_state

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


_weighted_cache: dict = {}


# GUI label -> position id accepted by render_frame.
CAPTION_POSITIONS = {"Top": "top", "Middle": "middle", "Bottom": "bottom"}


def _load_caption_font(size: int, font_path: str = "", weight: Optional[int] = None):
    """Return (font, stroke_width) for captions at the requested weight class.

    weight=None is the font's own weight and matches _load_font exactly.
    """
    if weight is None:
        return _load_font(size, font_path), 0
    key = (size, font_path, weight)
    if key in _weighted_cache:
        return _weighted_cache[key]
    path = font_path if font_path and os.path.exists(font_path) else next(
        (p for p in _FONT_CANDIDATES if os.path.exists(p)), ""
    )
    result = (_load_font(size, font_path), 0)
    if path:
        try:
            result = load_weighted_font(path, size, weight)
        except Exception:
            pass
    _weighted_cache[key] = result
    return result


def _text_width(font: ImageFont.ImageFont, text: str) -> int:
    try:
        return int(font.getlength(text))
    except AttributeError:
        return font.getsize(text)[0]  # type: ignore[attr-defined]


# How long a caption stays on screen after its segment ends (unless the next
# segment starts sooner).
_LINGER = 0.4


def _active_segment(segments: List[Segment], t: float) -> Optional[Segment]:
    """Return the segment active at time t, or the most recently ended one."""
    for seg in segments:
        if seg.start <= t < seg.end:
            return seg
    # Show segment for up to _LINGER seconds after it ends
    for seg in reversed(segments):
        if seg.start <= t and t < seg.end + _LINGER:
            return seg
        if seg.start <= t:
            break
    return None


def _visible_window(segments: List[Segment], seg: Segment) -> Tuple[float, float]:
    """Return (start, end) of the span during which seg's caption is on screen,
    mirroring _active_segment: it lingers after seg.end until the next segment
    begins, for at most _LINGER seconds."""
    end = seg.end + _LINGER
    for i, s in enumerate(segments):
        if s is seg:
            if i + 1 < len(segments):
                end = min(end, max(seg.end, segments[i + 1].start))
            break
    return seg.start, end


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
    font_weight: Optional[int] = None,
    transition: Optional[TextTransition] = None,
    position: str = "bottom",
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
        return _apply_watermark(frame.convert("RGBA")).convert("RGB")

    width, height = frame.size
    font, stroke = _load_caption_font(font_size, font_path, font_weight)
    space_w = _text_width(font, " ")
    line_h = int(font_size * 1.45) + 2 * stroke
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
        w = _text_width(font, word.text) + 2 * stroke
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
    # The caption (bar + words) is built as its own layer so a transition can
    # fade, slide or scale it as a unit before it's composited onto the frame.
    v_pad = 14
    text_area_h = len(lines) * line_h + 2 * v_pad
    if position == "top":
        bar_top = 0
    elif position == "middle":
        bar_top = (height - text_area_h) // 2
    else:
        bar_top = height - text_area_h

    caption = Image.new("RGBA", (width, text_area_h), (0, 0, 0, 185))

    # One coverage mask per colour, so antialiased edges blend exactly as if
    # the words had been drawn straight onto the frame.
    masks: dict = {}
    for li, line in enumerate(lines):
        if not line:
            continue
        last_wi, last_wt, last_xo = line[-1]
        line_width = last_xo + _text_width(font, last_wt) + 2 * stroke
        x_start = (width - line_width) // 2
        y = v_pad + li * line_h + stroke

        for wi, wt, xo in line:
            x = x_start + xo + stroke
            if wi < cur_wi:
                color = dim(text_color, 0.55)
            elif wi == cur_wi:
                color = highlight_color
            else:
                color = text_color
            if color not in masks:
                masks[color] = Image.new("L", caption.size, 0)
            ImageDraw.Draw(masks[color]).text(
                (x, y), wt, font=font, fill=255, stroke_width=stroke, stroke_fill=255,
            )

    for color, mask in masks.items():
        layer = Image.new("RGBA", caption.size, tuple(color) + (0,))
        layer.putalpha(mask)
        caption.alpha_composite(layer)

    if text_area_h > height:
        # Caption is taller than the frame: keep the part nearest the anchor
        # edge (middle trims both ends evenly).
        overflow = text_area_h - height
        crop_top = {"top": 0, "middle": overflow // 2}.get(position, overflow)
        caption = caption.crop((0, crop_top, width, crop_top + height))
        bar_top = 0

    seg_start, seg_end = _visible_window(segments, seg)
    style, progress = transition_state(transition, seg_start, seg_end, t)
    frame_rgba = composite_caption(
        frame.convert("RGBA"), caption, bar_top, style, progress, position,
    )

    return _apply_watermark(frame_rgba).convert("RGB")
