"""Caption background bar shapes: hard edge, fade, rounded and feathered."""
from typing import Tuple

from PIL import Image, ImageDraw, ImageFilter

# Display name -> internal style id.
CAPTION_EDGE_STYLES = {
    "Hard": "hard",
    "Fade": "fade",
    "Rounded": "rounded",
    "Feather": "feather",
}

_SUPERSAMPLE = 4


def _smoothstep(x: float) -> float:
    return x * x * (3.0 - 2.0 * x)


def bar_margins(style: str, size: int, position: str) -> Tuple[int, int]:
    """Extra rows (above, below) the bar needs beyond the text area so the
    edge effect doesn't eat into the text. Fade only softens the edge facing
    the video; feather softens every edge."""
    if size <= 0:
        return 0, 0
    if style == "fade":
        if position == "top":
            return 0, size
        if position == "middle":
            return size, size
        return size, 0
    if style == "feather":
        return size, size
    return 0, 0


def build_bar(
    width: int,
    text_h: int,
    opacity: float,
    style: str = "hard",
    size: int = 0,
    position: str = "bottom",
) -> Tuple[Image.Image, int]:
    """Return (RGBA black bar layer, rows above the text area).

    The layer is width x (text_h + margins); the text area starts at the
    returned row offset."""
    alpha = int(round(max(0.0, min(1.0, opacity)) * 255))
    size = max(0, int(size))
    top, bottom = bar_margins(style, size, position)
    h = text_h + top + bottom

    if style == "fade" and size > 0:
        col = [alpha] * h
        for y in range(top):
            col[y] = int(round(alpha * _smoothstep(y / top)))
        for y in range(bottom):
            col[h - 1 - y] = int(round(alpha * _smoothstep(y / bottom)))
        mask = Image.new("L", (1, h))
        mask.putdata(col)
        mask = mask.resize((width, h))
    elif style in ("rounded", "feather") and size > 0:
        s = _SUPERSAMPLE
        inset = min(size, width // 4)
        box = (inset * s, top * s, (width - inset) * s, (top + text_h) * s)
        big = Image.new("L", (width * s, h * s), 0)
        ImageDraw.Draw(big).rounded_rectangle(
            box, radius=min(size * s, text_h * s // 2), fill=alpha,
        )
        mask = big.resize((width, h), Image.LANCZOS)
        if style == "feather":
            mask = mask.filter(ImageFilter.GaussianBlur(size / 2.0))
    else:
        mask = Image.new("L", (width, h), alpha)

    bar = Image.new("RGBA", (width, h), (0, 0, 0, 0))
    bar.putalpha(mask)
    return bar, top
