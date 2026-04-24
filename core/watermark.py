import os
from dataclasses import dataclass, field
from typing import Optional, Tuple

from PIL import Image, ImageDraw


@dataclass
class WatermarkConfig:
    text: str = ""
    image_path: str = ""
    position: str = "bottom-right"   # "top-left" | "top-right" | "bottom-left" | "bottom-right"
    opacity: float = 0.70             # 0.0 – 1.0
    font_size: int = 28
    font_path: str = ""
    color: Tuple[int, int, int] = field(default_factory=lambda: (255, 255, 255))
    padding: int = 20


def build_watermark(
    config: WatermarkConfig,
    frame_size: Tuple[int, int],
) -> Optional[Image.Image]:
    """Return a full-frame RGBA overlay with the watermark, or None if nothing to draw.

    Pre-compute this once per generation; composite onto every frame cheaply.
    """
    if not config.text.strip() and not config.image_path.strip():
        return None

    fw, fh = frame_size
    alpha = int(max(0.0, min(1.0, config.opacity)) * 255)
    elements: list[Image.Image] = []

    # ---- Image element -------------------------------------------------------
    if config.image_path.strip() and os.path.exists(config.image_path.strip()):
        try:
            img = Image.open(config.image_path.strip()).convert("RGBA")
            max_w = max(32, int(fw * 0.12))
            if img.width > max_w:
                scale = max_w / img.width
                img = img.resize((max_w, max(1, int(img.height * scale))), Image.LANCZOS)
            r, g, b, a = img.split()
            a = a.point(lambda v: int(v * config.opacity))
            img.putalpha(a)
            elements.append(img)
        except Exception:
            pass

    # ---- Text element --------------------------------------------------------
    if config.text.strip():
        from core.renderer import _load_font  # reuse cached font loader
        font = _load_font(config.font_size, config.font_path)
        text = config.text.strip()

        dummy_draw = ImageDraw.Draw(Image.new("RGBA", (1, 1)))
        bbox = dummy_draw.textbbox((0, 0), text, font=font)
        tw = bbox[2] - bbox[0] + 6
        th = bbox[3] - bbox[1] + 6

        text_img = Image.new("RGBA", (tw, th), (0, 0, 0, 0))
        td = ImageDraw.Draw(text_img)
        td.text(
            (3, 3), text, font=font,
            fill=config.color + (alpha,),
            stroke_width=1,
            stroke_fill=(0, 0, 0, alpha // 2),
        )
        elements.append(text_img)

    if not elements:
        return None

    # ---- Combine elements vertically -----------------------------------------
    gap = 8
    total_h = sum(e.size[1] for e in elements) + gap * (len(elements) - 1)
    total_w = max(e.size[0] for e in elements)
    combined = Image.new("RGBA", (total_w, total_h), (0, 0, 0, 0))
    y_off = 0
    for elem in elements:
        x_off = (total_w - elem.size[0]) // 2
        combined.paste(elem, (x_off, y_off), elem)
        y_off += elem.size[1] + gap

    # ---- Place on full-frame canvas ------------------------------------------
    cw, ch = combined.size
    x = (fw - cw - config.padding) if "right" in config.position else config.padding
    y = (fh - ch - config.padding) if "bottom" in config.position else config.padding

    canvas = Image.new("RGBA", (fw, fh), (0, 0, 0, 0))
    canvas.paste(combined, (x, y), combined)
    return canvas
