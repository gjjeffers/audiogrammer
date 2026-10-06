import subprocess
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple


def _get_assets_dir() -> Path:
    """Return the assets/fonts directory, handling both normal and PyInstaller frozen runs."""
    if getattr(sys, "frozen", False):
        # Running as a PyInstaller EXE — assets are unpacked to sys._MEIPASS
        return Path(sys._MEIPASS) / "assets" / "fonts"
    # Normal Python run — use path relative to this source file
    return Path(__file__).parent.parent / "assets" / "fonts"


def discover_fonts() -> Dict[str, str]:
    """Return {display_name: abs_path} for all usable TTF/OTF fonts, sorted."""
    fonts: Dict[str, str] = {}
    assets_dir = _get_assets_dir()

    # 1. fc-list (Linux/macOS with fontconfig)
    try:
        out = subprocess.run(["fc-list"], capture_output=True, text=True, timeout=10).stdout
        for line in out.splitlines():
            parts = line.strip().split(":")
            if len(parts) < 2:
                continue
            path = parts[0].strip()
            if Path(path).suffix.lower() not in {".ttf", ".otf", ".ttc"}:
                continue
            family = parts[1].strip().split(",")[0].strip()
            style = ""
            for p in parts[2:]:
                if p.strip().startswith("style="):
                    style = p.strip()[6:].split(",")[0].strip()
                    break
            if style and style not in ("Regular", "Book", "Roman", "Medium", ""):
                display = f"{family} {style}"
            else:
                display = family
            if display and Path(path).exists():
                fonts[display] = path
    except Exception:
        pass

    # 2. Directory scan fallback (when fc-list unavailable)
    if not fonts:
        for d in ["/usr/share/fonts", "/Library/Fonts", "C:/Windows/Fonts"]:
            p = Path(d)
            if p.exists():
                for f in p.rglob("*.ttf"):
                    fonts[f.stem.replace("-", " ")] = str(f)

    # 3. Always include bundled fonts (guaranteed fallback)
    if assets_dir.exists():
        for f in sorted(assets_dir.glob("*.ttf")):
            name = f.stem.replace("-", " ")
            if name not in fonts:
                fonts[name] = str(f)

    return dict(sorted(fonts.items()))


# ---------------------------------------------------------------------------
# Font weight
# ---------------------------------------------------------------------------

# Display name -> CSS / OpenType weight class. "Font Default" (None) renders the
# selected face exactly as-is.
FONT_DEFAULT_WEIGHT = "Font Default"
FONT_WEIGHTS: Dict[str, Optional[int]] = {
    FONT_DEFAULT_WEIGHT: None,
    "Thin": 100,
    "Extra Light": 200,
    "Light": 300,
    "Regular": 400,
    "Medium": 500,
    "Semi Bold": 600,
    "Bold": 700,
    "Extra Bold": 800,
    "Black": 900,
}

# Style-name tokens (lowercased, spaces/hyphens removed) -> weight class.
_STYLE_WEIGHTS = {
    "thin": 100, "hairline": 100,
    "extralight": 200, "ultralight": 200,
    "light": 300,
    "regular": 400, "normal": 400, "book": 400, "roman": 400,
    "medium": 500,
    "semibold": 600, "demibold": 600, "demi": 600,
    "bold": 700,
    "extrabold": 800, "ultrabold": 800,
    "black": 900, "heavy": 900,
}

# Extra synthetic stroke, as a fraction of the font size, per 100 weight units
# beyond the heaviest real face available. Calibrated so Regular -> Bold adds
# roughly the stem thickness difference of a typical sans-serif.
_STROKE_PER_100 = 0.008

_face_info_cache: Dict[str, Optional[Tuple[str, str, int]]] = {}
_family_cache: Dict[Tuple[str, str, Tuple[str, ...]], List[Tuple[int, str]]] = {}


def style_weight(style: str) -> Tuple[int, Tuple[str, ...]]:
    """Split a style name into (weight_class, remaining_variant_tokens).

    "Bold Italic" -> (700, ("italic",)); "SemiBold" -> (600, ()). Two-word
    weights ("Extra Bold", "Semi Bold") are recognised as well as compound ones.
    """
    tokens = [t for t in style.lower().replace("-", " ").replace("_", " ").split() if t]
    weight = 400
    variant: List[str] = []
    i = 0
    while i < len(tokens):
        pair = tokens[i] + tokens[i + 1] if i + 1 < len(tokens) else ""
        if pair in _STYLE_WEIGHTS:
            weight = _STYLE_WEIGHTS[pair]
            i += 2
            continue
        if tokens[i] in _STYLE_WEIGHTS:
            weight = _STYLE_WEIGHTS[tokens[i]]
        else:
            variant.append(tokens[i])
        i += 1
    return weight, tuple(sorted(variant))


def _face_info(path: str) -> Optional[Tuple[str, str, int]]:
    """Return (family, style, weight_class) for a font file, or None if unreadable."""
    if path in _face_info_cache:
        return _face_info_cache[path]
    info = None
    try:
        from PIL import ImageFont
        family, style = ImageFont.truetype(path, 12).getname()
        if family:
            info = (family, style or "", style_weight(style or "")[0])
    except Exception:
        info = None
    _face_info_cache[path] = info
    return info


def _family_faces(font_path: str) -> List[Tuple[int, str]]:
    """Return sorted [(weight_class, path)] for faces sharing font_path's family.

    Faces of a family are installed side by side, so only font_path's own
    directory is scanned. Faces must also share the non-weight style tokens
    (italic, condensed, …) so picking a weight never changes the slant or width.
    """
    info = _face_info(font_path)
    if info is None:
        return []
    family, style, _ = info
    variant = style_weight(style)[1]
    key = (str(Path(font_path).parent), family, variant)
    if key in _family_cache:
        return _family_cache[key]
    faces: List[Tuple[int, str]] = []
    for p in sorted(Path(font_path).parent.iterdir()):
        if p.suffix.lower() not in {".ttf", ".otf"}:
            continue
        other = _face_info(str(p))
        if other is None or other[0] != family or style_weight(other[1])[1] != variant:
            continue
        faces.append((other[2], str(p)))
    faces.sort()
    _family_cache[key] = faces
    return faces


def _nearest_face(faces: List[Tuple[int, str]], weight: int) -> Tuple[int, str]:
    # Ties go to the heavier face so a synthetic stroke is never needed when a
    # real face could cover the difference.
    return min(faces, key=lambda f: (abs(f[0] - weight), -f[0]))


def _set_variable_weight(font, weight: int) -> Optional[int]:
    """Set a variable font's weight axis. Returns the applied weight, or None
    if the font has no weight axis."""
    try:
        axes = font.get_variation_axes()
    except Exception:
        return None
    values = []
    applied = None
    for axis in axes:
        name = axis.get("name")
        if isinstance(name, bytes):
            name = name.decode("latin-1", "ignore")
        if applied is None and str(name).strip().lower() == "weight":
            applied = int(max(axis["minimum"], min(axis["maximum"], weight)))
            values.append(applied)
        else:
            values.append(axis["default"])
    if applied is None:
        return None
    try:
        font.set_variation_by_axes(values)
    except Exception:
        return None
    return applied


def load_weighted_font(font_path: str, size: int, weight: Optional[int]):
    """Load font_path at size, adjusted towards the requested weight class.

    Returns (font, stroke_width). Resolution order:
      1. Variable fonts with a weight axis are set to that weight directly.
      2. Otherwise the nearest real face of the same family is used.
      3. If the request is heavier than any available face, the difference is
         made up with a synthetic stroke (stroke_width > 0) drawn in the text
         colour. Lighter-than-available requests use the lightest face.
    weight=None loads font_path unchanged with no stroke.
    """
    from PIL import ImageFont

    font = ImageFont.truetype(font_path, size)
    if weight is None:
        return font, 0

    achieved = _set_variable_weight(font, weight)
    if achieved is None:
        faces = _family_faces(font_path)
        if faces:
            achieved, face_path = _nearest_face(faces, weight)
            if face_path != font_path:
                font = ImageFont.truetype(face_path, size)
        else:
            achieved = style_weight(font.getname()[1] or "")[0]

    stroke = 0
    if weight > achieved:
        stroke = int(round(size * _STROKE_PER_100 * (weight - achieved) / 100))
    return font, stroke
