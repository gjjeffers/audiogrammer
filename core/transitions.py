from dataclasses import dataclass
from typing import Optional, Tuple

from PIL import Image

# Display name -> internal style id. The same list is offered for both the
# "in" (text appearing) and "out" (text leaving) transitions.
TRANSITION_STYLES = {
    "None": "none",
    "Fade": "fade",
    "Slide": "slide",
    "Zoom": "zoom",
}

# Zoom transitions start/end the caption at this fraction of its full size.
_ZOOM_MIN_SCALE = 0.6


@dataclass
class TextTransition:
    in_style: str = "none"
    out_style: str = "none"
    duration: float = 0.3  # seconds per transition


def _ease_out(p: float) -> float:
    return 1.0 - (1.0 - p) ** 3


def transition_state(
    transition: Optional[TextTransition],
    visible_start: float,
    visible_end: float,
    t: float,
) -> Tuple[str, float]:
    """Return (style, progress) for a caption visible over [visible_start, visible_end).

    progress runs 0 -> 1 as the caption becomes fully visible, so an "in"
    transition ramps up from visible_start and an "out" transition ramps down
    to 0 at visible_end. ("none", 1.0) means draw the caption normally.
    Each transition is capped at half the visible span so in and out never
    overlap on short captions.
    """
    if transition is None or transition.duration <= 0:
        return "none", 1.0
    dur = min(transition.duration, (visible_end - visible_start) / 2)
    if dur <= 0:
        return "none", 1.0

    if transition.in_style != "none" and t < visible_start + dur:
        p = max(0.0, (t - visible_start) / dur)
        return transition.in_style, _ease_out(p)
    if transition.out_style != "none" and t > visible_end - dur:
        p = max(0.0, (visible_end - t) / dur)
        return transition.out_style, _ease_out(p)
    return "none", 1.0


def _scale_alpha(layer: Image.Image, factor: float) -> Image.Image:
    alpha = layer.getchannel("A").point(lambda a: int(a * factor))
    layer = layer.copy()
    layer.putalpha(alpha)
    return layer


def composite_caption(
    frame: Image.Image,
    caption: Image.Image,
    top: int,
    style: str,
    progress: float,
    position: str = "bottom",
) -> Image.Image:
    """Alpha-composite the caption layer onto frame (RGBA) at y=top, applying
    the given transition style at progress (0 = hidden, 1 = fully shown).

    - fade:  caption opacity follows progress.
    - slide: caption moves in from (or out to) the bottom edge of the frame,
             or the top edge when position is "top".
    - zoom:  caption grows from (or shrinks to) its centre while fading.
    """
    if style == "none" or progress >= 1.0:
        frame.alpha_composite(caption, (0, top))
        return frame
    if progress <= 0.0:
        return frame

    if style == "fade":
        frame.alpha_composite(_scale_alpha(caption, progress), (0, top))
    elif style == "slide" and position == "top":
        offset = int(round((1.0 - progress) * (top + caption.height)))
        if offset < caption.height:
            visible = caption.crop((0, offset, caption.width, caption.height))
            frame.alpha_composite(visible, (0, top))
    elif style == "slide":
        offset = int(round((1.0 - progress) * (frame.height - top)))
        if top + offset < frame.height:
            # Crop the part that has risen into view; alpha_composite can't
            # take a source that hangs off the bottom of the frame.
            visible = caption.crop((0, 0, caption.width, frame.height - top - offset))
            frame.alpha_composite(visible, (0, top + offset))
    elif style == "zoom":
        scale = _ZOOM_MIN_SCALE + (1.0 - _ZOOM_MIN_SCALE) * progress
        w = max(1, int(round(caption.width * scale)))
        h = max(1, int(round(caption.height * scale)))
        scaled = _scale_alpha(caption.resize((w, h), Image.BILINEAR), progress)
        x = (caption.width - w) // 2
        y = top + (caption.height - h) // 2
        frame.alpha_composite(scaled, (x, y))
    else:
        frame.alpha_composite(caption, (0, top))
    return frame
